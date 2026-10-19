"""Read-only benchmark: synthetic questions, stage timings, model metrics and evidence."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from time import perf_counter

from catalina_ingestion.clients.ollama import close_ollama_client, open_ollama_client
from catalina_ingestion.clients.qdrant import close_qdrant_client, open_qdrant_client
from catalina_ingestion.db.postgres import close_postgres_pool, open_postgres_pool
from catalina_ingestion.domain.conversations import Message
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.chat import ChatService
from catalina_ingestion.services.generation import GenerationService


async def run(question, suite, repeat, document_mode):
    await open_postgres_pool()
    await open_ollama_client()
    await open_qdrant_client()
    original = GenerationService.chat
    events = []

    async def measured(self, **kwargs):
        start = perf_counter()
        print(json.dumps({"event": "model_start", "characters": sum(
            len(m["content"]) for m in kwargs["messages"]
        )}), flush=True)
        text, metrics = await original(self, **kwargs)
        events.append({
            "stage": "routing" if "route" in kwargs.get(
                "output_schema", {},
            ).get("properties", {}) else "generation",
            "seconds": round(perf_counter() - start, 3),
            "input_characters": sum(len(m["content"]) for m in kwargs["messages"]),
            "prompt_tokens": metrics.prompt_eval_count,
            "prompt_seconds": round(metrics.prompt_eval_duration_ns / 1e9, 3),
            "output_tokens": metrics.eval_count,
            "output_seconds": round(metrics.eval_duration_ns / 1e9, 3),
            "load_seconds": round(metrics.load_duration_ns / 1e9, 3),
        })
        print(json.dumps({"event": "model_end", **events[-1]}), flush=True)
        return text, metrics

    GenerationService.chat = measured
    chat = ChatService()
    if document_mode:
        chat.rag_service.document_response_mode = document_mode
    print(json.dumps({"event": "configuration", "document_mode":
                      chat.rag_service.document_response_mode}), flush=True)
    original_build = chat.rag_service.retrieval_service.build

    async def build(query):
        start = perf_counter()
        context = await original_build(query)
        events.append({
            "stage": "retrieval", "seconds": round(perf_counter() - start, 3),
            "enabled": context.enabled, "characters": context.character_count,
            "evidence": json.loads(context.text) if context.text else None,
        })
        return context

    chat.rag_service.retrieval_service.build = build
    questions = [question] if not suite else [
        "Hola", "¿Cuánto es 17 por 6?",
        "Dime de que trata el reglamento estudiantil",
        "¿Qué dice el reglamento estudiantil sobre las faltas disciplinarias?",
        "¿Y sobre los derechos de los estudiantes?",
        "¿Cuánto cuesta la matrícula en el año 2099?",
        "Ahora dame tres consejos generales para estudiar mejor",
    ]
    if repeat:
        questions.append(questions[3] if suite else questions[0])
    history = []
    try:
        for index, current in enumerate(questions):
            events.clear()
            start = perf_counter()
            print(json.dumps({"event": "start", "question": current}), flush=True)
            try:
                answer = await chat.answer(RetrievalQuery(query=current), history=history)
                result = {
                    "question": current, "seconds": round(perf_counter() - start, 3),
                    "answer": answer.text, "reason": answer.reason.value,
                    "sources": [s.document_name for s in answer.citations], "events": events,
                }
                history.append(Message(
                    id=index + 1, conversacion_id=0, pregunta=current, respuesta=answer.text,
                    modelo=answer.model, tiempo_respuesta=None, fecha=datetime.now(UTC),
                ))
            except Exception as error:
                result = {"question": current, "seconds": round(perf_counter() - start, 3),
                          "error": str(error), "events": events}
            print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        GenerationService.chat = original
        await close_qdrant_client()
        await close_ollama_client()
        await close_postgres_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default="Dime de que trata el reglamento estudiantil")
    parser.add_argument("--suite", action="store_true")
    parser.add_argument("--repeat", action="store_true")
    parser.add_argument("--document-mode", choices=["generated", "extractive"])
    args = parser.parse_args()
    asyncio.run(run(args.question, args.suite, args.repeat, args.document_mode))
