import asyncio
import json
from contextlib import AsyncExitStack
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
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.vector_search import VectorSearchService

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = ROOT / "evaluation" / "corpus" / "manifest.json"

QUESTIONS_PATH = ROOT / "evaluation" / "datasets" / "questions.jsonl"


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_questions():
    questions = []

    for line in QUESTIONS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            questions.append(json.loads(line))

    return questions


async def build_document_map(manifest):
    mapping = {}

    async with postgres_connection() as connection:
        for document in manifest["documents"]:
            cursor = await connection.execute(
                """
                SELECT
                    d.id,
                    v.id
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
                continue

            mapping[row[0]] = {
                "corpus_id": document["corpus_id"],
                "code": document["code"],
                "version_id": row[1],
            }

    return mapping


async def main():
    manifest = load_manifest()
    questions = load_questions()

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        document_map = await build_document_map(manifest)

        service = VectorSearchService()

        print()
        print("========================================")
        print(" FASE 5.12.3 - DIAGNOSTICO DE SCORES")
        print("========================================")

        positive_scores = []
        negative_scores = []

        for question in questions:
            query = RetrievalQuery(
                query=question["question"],
                top_k=5,
                candidate_k=20,
                score_threshold=0.0,
            )

            result = await service.search(query)

            ranked = sorted(
                result.chunks,
                key=lambda chunk: (
                    -chunk.score,
                    chunk.point_id,
                ),
            )

            print()
            print("========================================")
            print(f"{question['question_id']} - {question['question']}")
            print("========================================")

            print(f"candidatos={result.count}")

            if not ranked:
                print("SIN CANDIDATOS")
                continue

            best_score = ranked[0].score

            print(f"best_score={best_score:.6f}")

            if question.get("should_answer") is False:
                negative_scores.append(best_score)
            else:
                positive_scores.append(best_score)

            print("TOP 10:")

            for position, chunk in enumerate(
                ranked[:10],
                start=1,
            ):
                corpus = document_map.get(chunk.document_id)

                if corpus is None:
                    corpus_id = "NO_CORPUS"
                    code = "NO_CORPUS"
                else:
                    corpus_id = corpus["corpus_id"]
                    code = corpus["code"]

                print(
                    f"{position:02d}. "
                    f"score={chunk.score:.6f} | "
                    f"{corpus_id} | "
                    f"{code} | "
                    f"doc={chunk.document_id} | "
                    f"version={chunk.version} | "
                    f"pages="
                    f"{chunk.page_start}-"
                    f"{chunk.page_end}"
                )

                preview = " ".join(chunk.text.split())

                print(f"    {preview[:180]}")

        print()
        print("========================================")
        print(" DISTRIBUCION GENERAL")
        print("========================================")

        if positive_scores:
            print(f"positivas_best_min={min(positive_scores):.6f}")
            print(f"positivas_best_max={max(positive_scores):.6f}")
            print(f"positivas_best_promedio={sum(positive_scores) / len(positive_scores):.6f}")

        if negative_scores:
            print(f"negativas_best_min={min(negative_scores):.6f}")
            print(f"negativas_best_max={max(negative_scores):.6f}")
            print(f"negativas_best_promedio={sum(negative_scores) / len(negative_scores):.6f}")

        print()
        print("DIAGNOSTICO DE SCORES: COMPLETADO")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
