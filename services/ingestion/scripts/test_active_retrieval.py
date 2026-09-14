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
from catalina_ingestion.domain.retrieval import (
    RetrievalFilter,
    RetrievalQuery,
)
from catalina_ingestion.services.vector_search import VectorSearchService


async def main() -> None:
    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        service = VectorSearchService()
        question = "¿Dónde puedo consultar el reglamento institucional?"

        permissive = await service.search(
            RetrievalQuery(
                query=question,
                score_threshold=0.0,
            )
        )

        print("PRUEBA 1: candidatos vigentes")
        print(f"candidatos={permissive.count}")
        print(f"descartados_por_cambio={permissive.discarded_after_recheck}")

        for chunk in permissive.chunks:
            print(f"documento={chunk.document_name}")
            print(f"version={chunk.version}")
            print(f"score={chunk.score:.6f}")
            print(f"paginas={chunk.page_start}-{chunk.page_end}")
            print(f"index_run_id={chunk.metadata['index_run_id']}")
            print(f"texto={chunk.text[:400]}")

        if not permissive.chunks:
            raise RuntimeError(
                "No se recuperó el documento de prueba esperado. "
                "Revisa estados, colección y puntuación."
            )

        strict = await service.search(
            RetrievalQuery(
                query=question,
                score_threshold=0.70,
            )
        )

        print()
        print("PRUEBA 2: umbral 0.70")
        print(f"candidatos={strict.count}")

        if any(chunk.score < 0.70 for chunk in strict.chunks):
            raise RuntimeError("No se respetó el umbral.")

        empty = await service.search(
            RetrievalQuery(
                query=question,
                score_threshold=0.0,
                filters=RetrievalFilter(document_id=2147483647),
            )
        )

        print()
        print("PRUEBA 3: documento inexistente")
        print(f"candidatos={empty.count}")

        if empty.chunks:
            raise RuntimeError("No se respetó el filtro documental.")

        print()
        print("BÚSQUEDA SOBRE EJECUCIONES ACTIVAS: OK")


if __name__ == "__main__":
    asyncio.run(main())
