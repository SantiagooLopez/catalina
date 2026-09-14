import asyncio
import json
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.clients.qdrant import (
    close_qdrant_client,
    open_qdrant_client,
)
from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
    postgres_connection,
)
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.retrieval_runtime import (
    ManagedRetrievalService,
)

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = ROOT / "evaluation" / "corpus" / "manifest.json"

QUESTIONS_PATH = ROOT / "evaluation" / "datasets" / "questions.jsonl"

RESULTS_DIRECTORY = ROOT / "evaluation" / "results"


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_questions():
    questions = []

    for line_number, line in enumerate(
        QUESTIONS_PATH.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            questions.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"JSON inválido en questions.jsonl línea {line_number}.") from error

    if not questions:
        raise RuntimeError("No existen preguntas de evaluación.")

    return questions


async def build_corpus_identity_map(manifest):
    identities = {}

    async with postgres_connection() as connection:
        for document in manifest["documents"]:
            cursor = await connection.execute(
                """
                SELECT
                    d.id,
                    v.id,
                    d.codigo,
                    d.nombre,
                    d.categoria,
                    v.version,
                    v.estado,
                    v.ejecucion_indexacion_activa_id
                FROM catalina.documentos AS d
                JOIN catalina.versiones_documentos AS v
                    ON v.documento_id = d.id
                WHERE d.codigo = %s
                  AND v.version = %s
                  AND d.estado = 'activo'
                  AND v.estado = 'activa'
                LIMIT 1
                """,
                (
                    document["code"],
                    document["version"],
                ),
            )

            row = await cursor.fetchone()

            if row is None:
                raise RuntimeError(
                    f"{document['corpus_id']} no posee una versión activa en PostgreSQL."
                )

            identities[row[0]] = {
                "corpus_id": document["corpus_id"],
                "document_id": row[0],
                "version_id": row[1],
                "code": row[2],
                "name": row[3],
                "category": row[4],
                "version": row[5],
                "state": row[6],
                "index_run_id": str(row[7]),
            }

    return identities


def evaluate_expectation(
    question,
    result,
    source_codes,
):
    should_answer = question.get("should_answer")

    expected_code = question.get("expected_document_code")

    if should_answer is None:
        return "unlabeled"

    if should_answer is False:
        if result.enabled:
            return "fail_should_abstain"

        return "pass"

    if not result.enabled:
        return "fail_should_answer"

    if expected_code is not None and expected_code not in source_codes:
        return "fail_wrong_source"

    return "pass"


async def evaluate_question(
    service,
    question,
    corpus_identities,
):
    query = RetrievalQuery(query=question["question"])

    started = perf_counter()

    result = await service.build(query)

    latency_ms = (perf_counter() - started) * 1000

    source_records = []
    source_codes = []
    non_corpus_sources = []

    for source in result.sources:
        corpus = corpus_identities.get(source.document_id)

        if corpus is None:
            corpus_id = None
            source_code = None

            non_corpus_sources.append(source.document_id)
        else:
            corpus_id = corpus["corpus_id"]
            source_code = corpus["code"]
            source_codes.append(source_code)

        source_records.append(
            {
                "citation_id": (source.citation_id),
                "point_id": source.point_id,
                "document_id": (source.document_id),
                "document_version_id": (source.document_version_id),
                "corpus_id": corpus_id,
                "document_code": source_code,
                "document_name": (source.document_name),
                "version": source.version,
                "page_start": (source.page_start),
                "page_end": source.page_end,
                "section": source.section,
                "index_run_id": (source.index_run_id),
            }
        )

    assessment = result.assessment

    expectation_status = evaluate_expectation(
        question,
        result,
        source_codes,
    )

    return {
        "question_id": (question["question_id"]),
        "question": question["question"],
        "category": question["category"],
        "question_type": (question["question_type"]),
        "expected": {
            "should_answer": (question.get("should_answer")),
            "document_code": (question.get("expected_document_code")),
            "version": (question.get("expected_version")),
            "evidence": (question.get("expected_evidence")),
        },
        "retrieval": {
            "enabled": result.enabled,
            "reason": result.reason,
            "latency_ms": round(
                latency_ms,
                3,
            ),
            "character_count": (result.character_count),
            "source_count": len(result.sources),
            "omitted_by_budget": (result.omitted_by_budget),
            "best_score": (assessment.best_score),
            "evaluated_chunks": (assessment.evaluated_chunks),
            "relevant_chunks": (assessment.relevant_chunks),
            "document_count": (assessment.document_count),
            "evidence_character_count": (assessment.character_count),
            "reasons": [reason.value for reason in assessment.reasons],
        },
        "policy": {
            "query_top_k": query.top_k,
            "query_candidate_k": (query.candidate_k),
            "query_score_threshold": (query.score_threshold),
            "minimum_chunk_score": (assessment.policy.minimum_chunk_score),
            "minimum_best_score": (assessment.policy.minimum_best_score),
            "minimum_chunks": (assessment.policy.minimum_chunks),
            "minimum_documents": (assessment.policy.minimum_documents),
            "minimum_characters": (assessment.policy.minimum_characters),
        },
        "sources": source_records,
        "source_document_codes": sorted(set(source_codes)),
        "non_corpus_document_ids": sorted(set(non_corpus_sources)),
        "corpus_contamination": bool(non_corpus_sources),
        "expectation_status": (expectation_status),
        "context_text": result.text,
    }


def print_result(record):
    retrieval = record["retrieval"]

    print()
    print("========================================")
    print(f"{record['question_id']} - {record['question']}")
    print("========================================")

    print(f"contexto_habilitado={retrieval['enabled']}")
    print(f"motivo={retrieval['reason']}")
    print(f"best_score={retrieval['best_score']}")
    print(f"fuentes={retrieval['source_count']}")
    print(f"documentos_relevantes={retrieval['document_count']}")
    print(f"latencia_ms={retrieval['latency_ms']}")
    print("evaluacion=" + ",".join(retrieval["reasons"]))

    print(f"documentos_corpus={record['source_document_codes']}")

    print(f"contaminacion_no_corpus={record['corpus_contamination']}")

    print(f"expectation_status={record['expectation_status']}")

    for source in record["sources"]:
        print(
            f"  {source['citation_id']} | "
            f"corpus_id={source['corpus_id']} | "
            f"document_id="
            f"{source['document_id']} | "
            f"code={source['document_code']} | "
            f"version={source['version']} | "
            f"pages="
            f"{source['page_start']}-"
            f"{source['page_end']}"
        )


async def main():
    manifest = load_manifest()
    questions = load_questions()

    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    output_path = RESULTS_DIRECTORY / f"institutional_rag_baseline_{timestamp}.jsonl"

    print()
    print("========================================")
    print(" FASE 5.12.3 - BASELINE RAG")
    print("========================================")
    print(f"preguntas={len(questions)}")

    records = []

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        corpus_identities = await build_corpus_identity_map(manifest)

        print(f"documentos_corpus_activos={len(corpus_identities)}")

        service = ManagedRetrievalService()

        for question in questions:
            record = await evaluate_question(
                service,
                question,
                corpus_identities,
            )

            records.append(record)
            print_result(record)

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        for record in records:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )
            file.write("\n")

    enabled = sum(record["retrieval"]["enabled"] for record in records)

    disabled = len(records) - enabled

    contaminated = sum(record["corpus_contamination"] for record in records)

    passed = sum(record["expectation_status"] == "pass" for record in records)

    failed = sum(record["expectation_status"].startswith("fail") for record in records)

    unlabeled = sum(record["expectation_status"] == "unlabeled" for record in records)

    latencies = [record["retrieval"]["latency_ms"] for record in records]

    average_latency = sum(latencies) / len(latencies)

    print()
    print("========================================")
    print(" RESUMEN BASELINE")
    print("========================================")

    print(f"preguntas={len(records)}")
    print(f"contexto_habilitado={enabled}")
    print(f"contexto_deshabilitado={disabled}")
    print(f"contaminadas_no_corpus={contaminated}")
    print(f"expectativas_pass={passed}")
    print(f"expectativas_fail={failed}")
    print(f"sin_etiquetar={unlabeled}")
    print(f"latencia_promedio_ms={average_latency:.3f}")
    print(f"resultado_jsonl={output_path}")

    print()
    print("FASE 5.12.3: BASELINE EJECUTADO")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
