"""Read-only live smoke check with synthetic history; never creates users or messages."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from time import perf_counter

from catalina_ingestion.clients.ollama import close_ollama_client, open_ollama_client
from catalina_ingestion.clients.qdrant import close_qdrant_client, open_qdrant_client
from catalina_ingestion.db.postgres import close_postgres_pool, open_postgres_pool
from catalina_ingestion.domain.conversations import Message
from catalina_ingestion.domain.generation import GenerationReason
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.answer_generation import AnswerGenerationService
from catalina_ingestion.services.chat import ChatService


class AuditedRag(AnswerGenerationService):
    def __init__(self):
        super().__init__()
        self.queries = []

    async def answer(self, query):
        self.queries.append(query.query)
        print(json.dumps({"event": "retrieval", "search_query": query.query},
                         ensure_ascii=False), flush=True)
        return await super().answer(query)


async def main(followup_only=False):
    await open_ollama_client()
    await open_qdrant_client()
    await open_postgres_pool()
    try:
        rag = AuditedRag()
        chat = ChatService(rag_service=rag)
        history = []
        cases = [
            ("Me llamo Ana y me gusta dibujar", "general"),
            ("¿Cómo me llamo y qué me gusta hacer?", "general"),
            ("Explícame por qué el cielo es azul", "general"),
            ("¿Qué servicios ofrece bienestar universitario a los estudiantes?", "university"),
            ("¿Y dónde queda esa dependencia?", "university"),
            ("Ahora dame tres consejos generales para estudiar mejor", "general"),
        ]
        if followup_only:
            history.append(Message(
                id=1, conversacion_id=0,
                pregunta="¿Qué servicios ofrece bienestar universitario a los estudiantes?",
                respuesta="Bienestar ofrece servicios de cultura, deporte y salud universitaria.",
                modelo=None, tiempo_respuesta=None, fecha=datetime.now(UTC),
            ))
            cases = cases[-2:]
        for question, expected in cases:
            before = len(rag.queries)
            started = perf_counter()
            answer = await chat.answer(RetrievalQuery(query=question), history=history)
            actual = "university" if (
                len(rag.queries) > before or answer.reason is GenerationReason.CAMPUS_LOCATION
            ) else "general"
            passed = actual == expected
            if expected == "general":
                passed = passed and answer.reason == GenerationReason.GENERAL_CHAT
            if "Cómo me llamo" in question:
                passed = (
                    passed and "ana" in answer.text.casefold() and "dibuj" in answer.text.casefold()
                )
            print(json.dumps({
                "question": question, "expected": expected, "route": actual,
                "passed": passed, "reason": answer.reason.value,
                "seconds": round(perf_counter() - started, 2),
                "search_query": rag.queries[-1] if actual == "university" else None,
                "citations": len(answer.citations), "answer": answer.text[:700],
            }, ensure_ascii=False), flush=True)
            if not passed:
                raise AssertionError(f"Falló el comportamiento conversacional: {question}")
            history.append(Message(
                id=len(history) + 1, conversacion_id=0, pregunta=question,
                respuesta=answer.text, modelo=answer.model,
                tiempo_respuesta=None, fecha=datetime.now(UTC),
            ))
    finally:
        await close_postgres_pool()
        await close_qdrant_client()
        await close_ollama_client()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--followup-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(followup_only=args.followup_only))
