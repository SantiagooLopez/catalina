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
from catalina_ingestion.domain.evidence import EvidencePolicy
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.evidence import (
    EvidenceRetrievalService,
)
from catalina_ingestion.services.rag_context import (
    RagContextService,
)
from catalina_ingestion.services.retrieval_runtime import (
    ManagedRetrievalService,
)

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = ROOT / "evaluation" / "corpus" / "manifest.json"

QUESTIONS_PATH = ROOT / "evaluation" / "datasets" / "questions.jsonl"

RESULTS_DIRECTORY = ROOT / "evaluation" / "results"


CONFIGURATIONS = (
    {
        "name": "A_actual",
        "query_score_threshold": 0.70,
        "minimum_chunk_score": 0.70,
        "minimum_best_score": 0.75,
    },
    {
        "name": "B_conservadora",
        "query_score_threshold": 0.50,
        "minimum_chunk_score": 0.50,
        "minimum_best_score": 0.55,
    },
    {
        "name": "C_balanceada",
        "query_score_threshold": 0.50,
        "minimum_chunk_score": 0.50,
        "minimum_best_score": 0.50,
    },
    {
        "name": "D_busqueda_amplia",
        "query_score_threshold": 0.45,
        "minimum_chunk_score": 0.50,
        "minimum_best_score": 0.55,
    },
)


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


async def build_corpus_map(manifest):
    mapping = {}

    async with postgres_connection() as connection:
        for document in manifest["documents"]:
            cursor = await connection.execute(
                """
                SELECT
                    d.id,
                    v.id,
                    d.codigo,
                    d.nombre,
                    v.version
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
                raise RuntimeError(f"{document['corpus_id']} no está activo en PostgreSQL.")

            mapping[row[0]] = {
                "corpus_id": document["corpus_id"],
                "document_id": row[0],
                "version_id": row[1],
                "code": row[2],
                "name": row[3],
                "version": row[4],
            }

    return mapping


def safe_ratio(numerator, denominator):
    if denominator == 0:
        return 0.0

    return numerator / denominator


def classify_case(
    should_answer,
    enabled,
):
    if should_answer:
        if enabled:
            return "TP"

        return "FN"

    if enabled:
        return "FP"

    return "TN"


async def evaluate_configuration(
    configuration,
    questions,
    corpus_map,
):
    policy = EvidencePolicy(
        minimum_chunk_score=(configuration["minimum_chunk_score"]),
        minimum_best_score=(configuration["minimum_best_score"]),
        minimum_chunks=1,
        minimum_documents=1,
        minimum_characters=80,
    )

    evidence_service = EvidenceRetrievalService(policy=policy)

    context_service = RagContextService(evidence_service=evidence_service)

    service = ManagedRetrievalService(context_service=context_service)

    records = []

    for question in questions:
        query = RetrievalQuery(
            query=question["question"],
            top_k=5,
            candidate_k=20,
            score_threshold=(configuration["query_score_threshold"]),
        )

        started = perf_counter()

        result = await service.build(query)

        latency_ms = (perf_counter() - started) * 1000

        source_records = []
        source_codes = []
        contamination = False

        for source in result.sources:
            corpus = corpus_map.get(source.document_id)

            if corpus is None:
                contamination = True
                source_code = None
                corpus_id = None
            else:
                source_code = corpus["code"]
                corpus_id = corpus["corpus_id"]
                source_codes.append(source_code)

            source_records.append(
                {
                    "citation_id": (source.citation_id),
                    "document_id": (source.document_id),
                    "document_version_id": (source.document_version_id),
                    "corpus_id": corpus_id,
                    "document_code": source_code,
                    "document_name": (source.document_name),
                    "version": source.version,
                    "page_start": (source.page_start),
                    "page_end": (source.page_end),
                    "section": source.section,
                }
            )

        expected_code = question.get("expected_document_code")

        expected_version = question.get("expected_version")

        source_match = False

        if result.enabled and expected_code:
            source_match = any(
                source["document_code"] == expected_code
                and (expected_version is None or source["version"] == expected_version)
                for source in source_records
            )

        classification = classify_case(
            question["should_answer"],
            result.enabled,
        )

        if question["should_answer"]:
            end_to_end_pass = result.enabled and source_match and not contamination
        else:
            end_to_end_pass = not result.enabled

        records.append(
            {
                "question_id": (question["question_id"]),
                "question": (question["question"]),
                "should_answer": (question["should_answer"]),
                "expected_document_code": (expected_code),
                "expected_version": (expected_version),
                "enabled": result.enabled,
                "reason": result.reason,
                "best_score": (result.assessment.best_score),
                "classification": (classification),
                "source_match": (source_match),
                "corpus_contamination": (contamination),
                "source_document_codes": (sorted(set(source_codes))),
                "sources": source_records,
                "latency_ms": round(
                    latency_ms,
                    3,
                ),
                "evidence_reasons": [reason.value for reason in result.assessment.reasons],
                "end_to_end_pass": (end_to_end_pass),
            }
        )

    tp = sum(record["classification"] == "TP" for record in records)

    fn = sum(record["classification"] == "FN" for record in records)

    tn = sum(record["classification"] == "TN" for record in records)

    fp = sum(record["classification"] == "FP" for record in records)

    positive_answers = [record for record in records if record["should_answer"]]

    answered_positives = [record for record in positive_answers if record["enabled"]]

    source_correct = sum(record["source_match"] for record in answered_positives)

    end_to_end_passes = sum(record["end_to_end_pass"] for record in records)

    contaminated = sum(record["corpus_contamination"] for record in records)

    latencies = [record["latency_ms"] for record in records]

    summary = {
        "configuration": configuration,
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
        "precision": safe_ratio(
            tp,
            tp + fp,
        ),
        "recall": safe_ratio(
            tp,
            tp + fn,
        ),
        "accuracy": safe_ratio(
            tp + tn,
            len(records),
        ),
        "source_accuracy_answered": (
            safe_ratio(
                source_correct,
                len(answered_positives),
            )
        ),
        "source_accuracy_all_positives": (
            safe_ratio(
                source_correct,
                len(positive_answers),
            )
        ),
        "end_to_end_accuracy": (
            safe_ratio(
                end_to_end_passes,
                len(records),
            )
        ),
        "contaminated_questions": (contaminated),
        "average_latency_ms": (sum(latencies) / len(latencies)),
    }

    return {
        "summary": summary,
        "questions": records,
    }


def print_configuration(result):
    summary = result["summary"]
    configuration = summary["configuration"]

    print()
    print("========================================")
    print(f" {configuration['name']}")
    print("========================================")

    print(f"query_score_threshold={configuration['query_score_threshold']}")
    print(f"minimum_chunk_score={configuration['minimum_chunk_score']}")
    print(f"minimum_best_score={configuration['minimum_best_score']}")

    print()

    for record in result["questions"]:
        print(
            f"{record['question_id']} | "
            f"{record['classification']} | "
            f"enabled={record['enabled']} | "
            f"best={record['best_score']} | "
            f"source_match="
            f"{record['source_match']} | "
            f"contamination="
            f"{record['corpus_contamination']} | "
            f"docs="
            f"{record['source_document_codes']}"
        )

    print()
    print(f"TP={summary['tp']} FN={summary['fn']} TN={summary['tn']} FP={summary['fp']}")

    print(f"precision={summary['precision']:.3f}")

    print(f"recall={summary['recall']:.3f}")

    print(f"accuracy={summary['accuracy']:.3f}")

    print(f"source_accuracy_answered={summary['source_accuracy_answered']:.3f}")

    print(f"source_accuracy_all_positives={summary['source_accuracy_all_positives']:.3f}")

    print(f"end_to_end_accuracy={summary['end_to_end_accuracy']:.3f}")

    print(f"contaminated_questions={summary['contaminated_questions']}")

    print(f"average_latency_ms={summary['average_latency_ms']:.3f}")


async def main():
    manifest = load_manifest()
    questions = load_questions()

    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        corpus_map = await build_corpus_map(manifest)

        print()
        print("========================================")
        print(" FASE 5.12.4 - CALIBRACION")
        print("========================================")
        print(f"preguntas={len(questions)}")
        print(f"documentos_corpus={len(corpus_map)}")

        results = []

        for configuration in CONFIGURATIONS:
            result = await evaluate_configuration(
                configuration,
                questions,
                corpus_map,
            )

            results.append(result)
            print_configuration(result)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    output_path = RESULTS_DIRECTORY / f"retrieval_calibration_{timestamp}.json"

    output_path.write_text(
        json.dumps(
            {
                "generated_at": timestamp,
                "question_count": len(questions),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    ranked = sorted(
        results,
        key=lambda item: (
            -item["summary"]["end_to_end_accuracy"],
            -item["summary"]["accuracy"],
            -item["summary"]["recall"],
            item["summary"]["contaminated_questions"],
            item["summary"]["average_latency_ms"],
        ),
    )

    print()
    print("========================================")
    print(" RANKING")
    print("========================================")

    for position, result in enumerate(
        ranked,
        start=1,
    ):
        summary = result["summary"]
        name = summary["configuration"]["name"]

        print(
            f"{position}. {name} | "
            f"end_to_end="
            f"{summary['end_to_end_accuracy']:.3f} | "
            f"accuracy="
            f"{summary['accuracy']:.3f} | "
            f"recall="
            f"{summary['recall']:.3f} | "
            f"FP={summary['fp']} | "
            f"FN={summary['fn']}"
        )

    print()
    print(f"resultado_json={output_path}")

    print()
    print("FASE 5.12.4: CALIBRACION EJECUTADA")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
