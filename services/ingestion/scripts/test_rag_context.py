import asyncio
from contextlib import AsyncExitStack

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
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.retrieval_runtime import (
    ManagedRetrievalService,
)


async def main():
    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        service = ManagedRetrievalService()

        questions = (
            "¿Dónde puedo consultar el reglamento institucional?",
            "¿Qué permite validar el documento de prueba del servicio de ingesta Catalina?",
        )

        for question in questions:
            result = await service.build(
                RetrievalQuery(
                    query=question,
                    score_threshold=0.0,
                )
            )

            print(f"pregunta={result.query}")
            print(f"contexto_habilitado={result.enabled}")
            print(f"motivo={result.reason}")
            print(f"caracteres={result.character_count}")
            print(f"fuentes={len(result.sources)}")
            print(f"omitidos_presupuesto={result.omitted_by_budget}")
            print("evaluacion=" + ",".join(reason.value for reason in result.assessment.reasons))

            if result.enabled:
                print(result.text)

            print()

        print("CONSTRUCCIÓN DE CONTEXTO: EJECUTADA")


if __name__ == "__main__":
    asyncio.run(main())
