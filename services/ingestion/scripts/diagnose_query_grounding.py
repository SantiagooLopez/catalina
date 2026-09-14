import asyncio
import json
import re
import unicodedata
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
)
from catalina_ingestion.domain.evidence import EvidencePolicy
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.evidence import (
    EvidenceRetrievalService,
)

ROOT = Path(__file__).resolve().parents[1]

QUESTIONS_PATH = ROOT / "evaluation" / "datasets" / "challenge_questions.jsonl"


STOPWORDS = {
    "a",
    "al",
    "como",
    "cual",
    "cuales",
    "de",
    "del",
    "el",
    "en",
    "es",
    "la",
    "las",
    "lo",
    "los",
    "para",
    "por",
    "que",
    "se",
    "un",
    "una",
    "y",
    "universidad",
    "catolica",
    "colombia",
}


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


def query_terms(question):
    normalized = normalize(question)

    terms = []

    for token in normalized.split():
        if token in STOPWORDS:
            continue

        if len(token) < 3:
            continue

        terms.append(token)

    return tuple(dict.fromkeys(terms))


def load_questions():
    rows = []

    for line in QUESTIONS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

    return rows


async def main():
    questions = load_questions()

    policy = EvidencePolicy(
        minimum_chunk_score=0.50,
        minimum_best_score=0.55,
        minimum_chunks=1,
        minimum_documents=1,
        minimum_characters=80,
    )

    service = EvidenceRetrievalService(policy=policy)

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        print()
        print("========================================")
        print(" DIAGNOSTICO QUERY GROUNDING")
        print("========================================")

        for question in questions:
            query = RetrievalQuery(
                query=question["question"],
                top_k=5,
                candidate_k=20,
                score_threshold=0.50,
            )

            evidence = await service.search(query)

            terms = query_terms(question["question"])

            evidence_text = normalize(" ".join(chunk.text for chunk in evidence.chunks))

            present = [term for term in terms if term in evidence_text]

            missing = [term for term in terms if term not in evidence_text]

            print()
            print("========================================")

            print(
                f"{question['question_id']} | "
                f"should_answer="
                f"{question['should_answer']} | "
                f"evidence_sufficient="
                f"{evidence.assessment.evidence_sufficient} | "
                f"best="
                f"{evidence.assessment.best_score}"
            )

            print(f"pregunta={question['question']}")

            print(f"terminos={list(terms)}")

            print(f"presentes={present}")

            print(f"ausentes={missing}")

            if evidence.chunks:
                print("chunks:")

                for index, chunk in enumerate(
                    evidence.chunks,
                    start=1,
                ):
                    preview = " ".join(chunk.text.split())

                    print(
                        f"  {index}. "
                        f"score={chunk.score:.6f} | "
                        f"doc={chunk.document_name} | "
                        f"pages="
                        f"{chunk.page_start}-"
                        f"{chunk.page_end}"
                    )

                    print(f"     {preview[:220]}")

    print()
    print("DIAGNOSTICO QUERY GROUNDING: COMPLETADO")


if __name__ == "__main__":
    asyncio.run(main())
