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
from catalina_ingestion.services.retrieval_runtime import (
    ManagedRetrievalService,
)

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = ROOT / "evaluation" / "corpus" / "manifest.json"

QUESTIONS_PATH = ROOT / "evaluation" / "datasets" / "challenge_questions.jsonl"

RESULTS_DIRECTORY = ROOT / "evaluation" / "results"

_DEFAULT_QUERY = RetrievalQuery(query="Consulta para leer defaults")
_DEFAULT_EVIDENCE_POLICY = EvidencePolicy()

QUERY_SCORE_THRESHOLD = _DEFAULT_QUERY.score_threshold
MINIMUM_CHUNK_SCORE = _DEFAULT_EVIDENCE_POLICY.minimum_chunk_score
MINIMUM_BEST_SCORE = _DEFAULT_EVIDENCE_POLICY.minimum_best_score


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
            raise RuntimeError(
                f"JSON inválido en challenge_questions.jsonl línea {line_number}."
            ) from error

    if not questions:
        raise RuntimeError("No existen preguntas challenge.")

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


def safe_ratio(
    numerator,
    denominator,
):
    if denominator == 0:
        return 0.0

    return numerator / denominator


def classify_case(
    should_answer,
    enabled,
):
    if should_answer:
        return "TP" if enabled else "FN"

    return "FP" if enabled else "TN"


async def evaluate_question(
    service,
    question,
    corpus_map,
):
    query = RetrievalQuery(
        query=question["question"],
        top_k=5,
        candidate_k=20,
        score_threshold=QUERY_SCORE_THRESHOLD,
    )

    started = perf_counter()

    result = await service.build(query)

    latency_ms = (perf_counter() - started) * 1000

    sources = []
    contamination = False

    for source in result.sources:
        corpus = corpus_map.get(source.document_id)

        if corpus is None:
            contamination = True
            corpus_id = None
            document_code = None
        else:
            corpus_id = corpus["corpus_id"]
            document_code = corpus["code"]

        sources.append(
            {
                "citation_id": (source.citation_id),
                "point_id": (source.point_id),
                "document_id": (source.document_id),
                "document_version_id": (source.document_version_id),
                "corpus_id": corpus_id,
                "document_code": document_code,
                "document_name": (source.document_name),
                "version": (source.version),
                "page_start": (source.page_start),
                "page_end": (source.page_end),
                "section": (source.section),
            }
        )

    expected_code = question.get("expected_document_code")

    expected_version = question.get("expected_version")

    top1_code = sources[0]["document_code"] if sources else None

    top1_version = sources[0]["version"] if sources else None

    source_match = False
    top1_match = False

    if result.enabled and expected_code:
        source_match = any(
            source["document_code"] == expected_code
            and (expected_version is None or source["version"] == expected_version)
            for source in sources
        )

        top1_match = top1_code == expected_code and (
            expected_version is None or top1_version == expected_version
        )

    classification = classify_case(
        question["should_answer"],
        result.enabled,
    )

    if question["should_answer"]:
        end_to_end_pass = result.enabled and source_match and top1_match and not contamination
    else:
        end_to_end_pass = not result.enabled

    grounding_reasons = []

    if result.grounding is not None:
        grounding_reasons = list(result.grounding.reasons)

    return {
        "question_id": (question["question_id"]),
        "question": (question["question"]),
        "question_type": (question["question_type"]),
        "should_answer": (question["should_answer"]),
        "expected_document_code": (expected_code),
        "expected_version": (expected_version),
        "enabled": (result.enabled),
        "reason": (result.reason),
        "best_score": (result.assessment.best_score),
        "classification": (classification),
        "source_match": (source_match),
        "top1_match": (top1_match),
        "top1_document_code": (top1_code),
        "corpus_contamination": (contamination),
        "grounding_reasons": (grounding_reasons),
        "evidence_reasons": [reason.value for reason in result.assessment.reasons],
        "sources": (sources),
        "latency_ms": round(
            latency_ms,
            3,
        ),
        "end_to_end_pass": (end_to_end_pass),
    }


async def main():
    manifest = load_manifest()
    questions = load_questions()

    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    service = ManagedRetrievalService()

    records = []

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
        print(" FASE 5.12.5 - GROUNDED RAG CHALLENGE")
        print("========================================")

        print(f"preguntas={len(questions)}")

        print(f"documentos_corpus={len(corpus_map)}")

        print(f"query_score_threshold={QUERY_SCORE_THRESHOLD}")

        print(f"minimum_chunk_score={MINIMUM_CHUNK_SCORE}")

        print(f"minimum_best_score={MINIMUM_BEST_SCORE}")

        for question in questions:
            record = await evaluate_question(
                service,
                question,
                corpus_map,
            )

            records.append(record)

            print()
            print(
                f"{record['question_id']} | "
                f"{record['classification']} | "
                f"enabled="
                f"{record['enabled']} | "
                f"reason="
                f"{record['reason']} | "
                f"best="
                f"{record['best_score']} | "
                f"top1="
                f"{record['top1_document_code']} | "
                f"top1_match="
                f"{record['top1_match']} | "
                f"pass="
                f"{record['end_to_end_pass']}"
            )

            print(f"  grounding={record['grounding_reasons']}")

            print(f"  evidence={record['evidence_reasons']}")

    tp = sum(record["classification"] == "TP" for record in records)

    fn = sum(record["classification"] == "FN" for record in records)

    tn = sum(record["classification"] == "TN" for record in records)

    fp = sum(record["classification"] == "FP" for record in records)

    positives = [record for record in records if record["should_answer"]]

    top1_correct = sum(record["top1_match"] for record in positives)

    source_correct = sum(record["source_match"] for record in positives)

    end_to_end_passes = sum(record["end_to_end_pass"] for record in records)

    contamination_count = sum(record["corpus_contamination"] for record in records)

    latencies = [record["latency_ms"] for record in records]

    precision = safe_ratio(
        tp,
        tp + fp,
    )

    recall = safe_ratio(
        tp,
        tp + fn,
    )

    accuracy = safe_ratio(
        tp + tn,
        len(records),
    )

    source_accuracy = safe_ratio(
        source_correct,
        len(positives),
    )

    top1_accuracy = safe_ratio(
        top1_correct,
        len(positives),
    )

    end_to_end_accuracy = safe_ratio(
        end_to_end_passes,
        len(records),
    )

    average_latency = sum(latencies) / len(latencies)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    output_path = RESULTS_DIRECTORY / (f"grounded_rag_challenge_{timestamp}.json")

    output_path.write_text(
        json.dumps(
            {
                "generated_at": timestamp,
                "policy": {
                    "query_score_threshold": (QUERY_SCORE_THRESHOLD),
                    "minimum_chunk_score": (MINIMUM_CHUNK_SCORE),
                    "minimum_best_score": (MINIMUM_BEST_SCORE),
                    "grounding_guard": True,
                },
                "summary": {
                    "tp": tp,
                    "fn": fn,
                    "tn": tn,
                    "fp": fp,
                    "precision": precision,
                    "recall": recall,
                    "accuracy": accuracy,
                    "source_accuracy": (source_accuracy),
                    "top1_accuracy": (top1_accuracy),
                    "end_to_end_accuracy": (end_to_end_accuracy),
                    "contamination_count": (contamination_count),
                    "average_latency_ms": (average_latency),
                },
                "questions": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("========================================")
    print(" RESUMEN GROUNDED RAG")
    print("========================================")

    print(f"TP={tp} FN={fn} TN={tn} FP={fp}")

    print(f"precision={precision:.3f}")

    print(f"recall={recall:.3f}")

    print(f"accuracy={accuracy:.3f}")

    print(f"source_accuracy={source_accuracy:.3f}")

    print(f"top1_accuracy={top1_accuracy:.3f}")

    print(f"end_to_end_accuracy={end_to_end_accuracy:.3f}")

    print(f"contamination_count={contamination_count}")

    print(f"average_latency_ms={average_latency:.3f}")

    print(f"resultado_json={output_path}")

    print()
    print("GROUNDED RAG CHALLENGE: EJECUTADO")


if __name__ == "__main__":
    asyncio.run(main())
