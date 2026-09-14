import asyncio
import json
import re
import unicodedata
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path

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
from catalina_ingestion.services.evidence import EvidenceRetrievalService

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = ROOT / "evaluation" / "corpus" / "manifest.json"

QUESTIONS_PATH = ROOT / "evaluation" / "datasets" / "challenge_questions.jsonl"

RESULTS_DIRECTORY = ROOT / "evaluation" / "results"

QUERY_SCORE_THRESHOLD = 0.50
MINIMUM_CHUNK_SCORE = 0.50
MINIMUM_BEST_SCORE = 0.55


def normalize(text):
    text = unicodedata.normalize(
        "NFKD",
        text.lower(),
    )

    text = "".join(character for character in text if not unicodedata.combining(character))

    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            text,
        )
    )


def simple_stem(token):
    token = normalize(token)

    if token.endswith("es") and len(token) > 5:
        return token[:-2]

    if token.endswith("s") and len(token) > 4:
        return token[:-1]

    return token


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_questions():
    rows = []

    for line_number, line in enumerate(
        QUESTIONS_PATH.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"JSON inválido en challenge línea {line_number}.") from error

    return rows


async def build_corpus_map(manifest):
    mapping = {}

    async with postgres_connection() as connection:
        for document in manifest["documents"]:
            cursor = await connection.execute(
                """
                SELECT
                    d.id,
                    d.codigo,
                    v.id,
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
                raise RuntimeError(f"{document['corpus_id']} no está activo.")

            mapping[row[0]] = {
                "corpus_id": (document["corpus_id"]),
                "code": row[1],
                "version_id": row[2],
                "version": row[3],
            }

    return mapping


def extract_years(question):
    return tuple(
        dict.fromkeys(
            re.findall(
                r"\b(?:19|20)\d{2}\b",
                question,
            )
        )
    )


def extract_location_anchors(question):
    matches = re.findall(
        (
            r"\ben\s+"
            r"([A-ZÁÉÍÓÚÑ]"
            r"[A-Za-zÁÉÍÓÚáéíóúÑñ-]+)"
            r"(?=[\s?.,]|$)"
        ),
        question,
    )

    ignored = {
        "Bogotá",
    }

    return tuple(value for value in dict.fromkeys(matches) if value not in ignored)


def extract_service_anchors(question):
    matches = re.findall(
        (
            r"\bservicio\s+de\s+"
            r"([A-Za-zÁÉÍÓÚáéíóúÑñ-]+)"
        ),
        question,
        flags=re.IGNORECASE,
    )

    return tuple(dict.fromkeys(matches))


def extract_regulation_scope(question):
    matches = re.findall(
        (
            r"\breglamento\s+de\s+"
            r"(?:(?:los|las|el|la)\s+)?"
            r"([A-Za-zÁÉÍÓÚáéíóúÑñ-]+)"
        ),
        question,
        flags=re.IGNORECASE,
    )

    return tuple(dict.fromkeys(matches))


def extract_acronyms(question):
    matches = re.findall(
        r"\b[A-ZÁÉÍÓÚÑ]{2,}\b",
        question,
    )

    ignored = {
        "D",
        "DC",
    }

    return tuple(value for value in dict.fromkeys(matches) if value not in ignored)


def scope_supported(
    target,
    chunks,
):
    target_stem = simple_stem(target)

    for chunk in chunks:
        title_tokens = {simple_stem(token) for token in normalize(chunk.document_name).split()}

        if target_stem in title_tokens:
            return True

        text_tokens = normalize(chunk.text).split()

        for index, token in enumerate(text_tokens):
            if not token.startswith("reglament"):
                continue

            window = {simple_stem(value) for value in text_tokens[index : index + 9]}

            if target_stem in window:
                return True

    return False


def apply_grounding_guard(
    question,
    chunks,
):
    combined_text = normalize(" ".join(chunk.text for chunk in chunks))

    reasons = []

    years = extract_years(question)

    for year in years:
        if year not in combined_text.split():
            reasons.append(f"missing_year:{year}")

    locations = extract_location_anchors(question)

    for location in locations:
        normalized_location = normalize(location)

        if normalized_location not in combined_text:
            reasons.append(f"missing_location:{normalized_location}")

    services = extract_service_anchors(question)

    for service in services:
        normalized_service = normalize(service)

        if normalized_service not in combined_text:
            reasons.append(f"missing_service:{normalized_service}")

    acronyms = extract_acronyms(question)

    for acronym in acronyms:
        normalized_acronym = normalize(acronym)

        if normalized_acronym not in combined_text:
            reasons.append(f"missing_identifier:{normalized_acronym}")

    scopes = extract_regulation_scope(question)

    for scope in scopes:
        if not scope_supported(
            scope,
            chunks,
        ):
            reasons.append(f"unsupported_regulation_scope:{normalize(scope)}")

    return (
        len(reasons) == 0,
        tuple(reasons),
    )


def classify_case(
    should_answer,
    enabled,
):
    if should_answer:
        return "TP" if enabled else "FN"

    return "FP" if enabled else "TN"


def safe_ratio(
    numerator,
    denominator,
):
    if denominator == 0:
        return 0.0

    return numerator / denominator


async def main():
    manifest = load_manifest()
    questions = load_questions()

    policy = EvidencePolicy(
        minimum_chunk_score=(MINIMUM_CHUNK_SCORE),
        minimum_best_score=(MINIMUM_BEST_SCORE),
        minimum_chunks=1,
        minimum_documents=1,
        minimum_characters=80,
    )

    service = EvidenceRetrievalService(policy=policy)

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
        print(" FASE 5.12.5 - GROUNDING GUARD")
        print("========================================")

        for question in questions:
            query = RetrievalQuery(
                query=question["question"],
                top_k=5,
                candidate_k=20,
                score_threshold=(QUERY_SCORE_THRESHOLD),
            )

            evidence = await service.search(query)

            retrieval_pass = evidence.assessment.evidence_sufficient

            if retrieval_pass:
                guard_pass, guard_reasons = apply_grounding_guard(
                    question["question"],
                    evidence.chunks,
                )
            else:
                guard_pass = False
                guard_reasons = ("retrieval_insufficient",)

            final_enabled = retrieval_pass and guard_pass

            if final_enabled:
                final_chunks = evidence.chunks
            else:
                final_chunks = ()

            source_codes = []

            for chunk in final_chunks:
                corpus = corpus_map.get(chunk.document_id)

                source_codes.append(corpus["code"] if corpus else None)

            top1_code = source_codes[0] if source_codes else None

            expected_code = question.get("expected_document_code")

            source_match = expected_code in source_codes if expected_code else False

            top1_match = top1_code == expected_code if expected_code else False

            classification = classify_case(
                question["should_answer"],
                final_enabled,
            )

            if question["should_answer"]:
                end_to_end_pass = final_enabled and source_match and top1_match
            else:
                end_to_end_pass = not final_enabled

            record = {
                "question_id": (question["question_id"]),
                "question": (question["question"]),
                "should_answer": (question["should_answer"]),
                "retrieval_pass": (retrieval_pass),
                "guard_pass": (guard_pass),
                "guard_reasons": list(guard_reasons),
                "final_enabled": (final_enabled),
                "best_score": (evidence.assessment.best_score),
                "classification": (classification),
                "top1_code": top1_code,
                "expected_code": expected_code,
                "source_match": source_match,
                "top1_match": top1_match,
                "end_to_end_pass": (end_to_end_pass),
            }

            records.append(record)

            print()
            print(
                f"{record['question_id']} | "
                f"{classification} | "
                f"retrieval="
                f"{retrieval_pass} | "
                f"guard={guard_pass} | "
                f"enabled="
                f"{final_enabled} | "
                f"best="
                f"{record['best_score']} | "
                f"top1={top1_code} | "
                f"pass="
                f"{end_to_end_pass}"
            )

            print(f"  guard_reasons={record['guard_reasons']}")

    tp = sum(record["classification"] == "TP" for record in records)

    fn = sum(record["classification"] == "FN" for record in records)

    tn = sum(record["classification"] == "TN" for record in records)

    fp = sum(record["classification"] == "FP" for record in records)

    positives = [record for record in records if record["should_answer"]]

    top1_correct = sum(record["top1_match"] for record in positives)

    end_to_end = sum(record["end_to_end_pass"] for record in records)

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

    top1_accuracy = safe_ratio(
        top1_correct,
        len(positives),
    )

    end_to_end_accuracy = safe_ratio(
        end_to_end,
        len(records),
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = RESULTS_DIRECTORY / f"grounding_guard_{timestamp}.json"

    output_path.write_text(
        json.dumps(
            {
                "generated_at": timestamp,
                "policy": {
                    "query_score_threshold": (QUERY_SCORE_THRESHOLD),
                    "minimum_chunk_score": (MINIMUM_CHUNK_SCORE),
                    "minimum_best_score": (MINIMUM_BEST_SCORE),
                },
                "summary": {
                    "tp": tp,
                    "fn": fn,
                    "tn": tn,
                    "fp": fp,
                    "precision": precision,
                    "recall": recall,
                    "accuracy": accuracy,
                    "top1_accuracy": (top1_accuracy),
                    "end_to_end_accuracy": (end_to_end_accuracy),
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
    print(" RESUMEN GROUNDING GUARD")
    print("========================================")

    print(f"TP={tp} FN={fn} TN={tn} FP={fp}")

    print(f"precision={precision:.3f}")

    print(f"recall={recall:.3f}")

    print(f"accuracy={accuracy:.3f}")

    print(f"top1_accuracy={top1_accuracy:.3f}")

    print(f"end_to_end_accuracy={end_to_end_accuracy:.3f}")

    print(f"resultado_json={output_path}")

    print()
    print("GROUNDING GUARD: EVALUADO")


if __name__ == "__main__":
    asyncio.run(main())
