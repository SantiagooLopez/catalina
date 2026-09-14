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
from catalina_ingestion.services.retrieval_selection import (
    RetrievalSelectionService,
)


async def main():
    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        service = RetrievalSelectionService()

        for threshold in (0.0, 0.70):
            query = RetrievalQuery(
                query=("¿Dónde puedo consultar el reglamento institucional?"),
                top_k=1,
                candidate_k=5,
                score_threshold=threshold,
            )

            result = await service.search(query)

            if result.count > query.top_k:
                raise RuntimeError("Se superó top_k.")

            if any(chunk.score < threshold for chunk in result.chunks):
                raise RuntimeError("No se respetó el umbral.")

            print(f"umbral={threshold}")
            print(f"candidatos_validos={result.candidate_count}")
            print(f"seleccionados={result.count}")
            print(f"mejor_score={result.best_score}")
            print(f"descartados_top_k={result.removed_by_top_k}")
            print(f"duplicados={result.removed_duplicates}")
            print(f"descartados_diversidad={result.removed_by_diversity}")

            for chunk in result.chunks:
                print(f"documento={chunk.document_name}")
                print(f"score={chunk.score:.6f}")

            print()

        print("BÚSQUEDA Y SELECCIÓN: OK")


if __name__ == "__main__":
    asyncio.run(main())
