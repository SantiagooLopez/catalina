import asyncio
import math

from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.core.config import get_settings
from catalina_ingestion.services.embeddings import EmbeddingService
from catalina_ingestion.services.query_embedding import QueryEmbeddingService


async def main() -> None:
    settings = get_settings()

    try:
        client = await open_ollama_client()

        service = QueryEmbeddingService(
            embedding_service=EmbeddingService(
                settings=settings,
                client=client,
            )
        )

        result = await service.generate("  ¿Dónde puedo consultar   el reglamento estudiantil?  ")

        if len(result.vector) != settings.embedding_dimension:
            raise RuntimeError("La dimensión de la consulta es incorrecta.")

        norm = math.hypot(*result.vector)

        print(f"consulta={result.normalized_query}")
        print(f"modelo={result.model}")
        print(f"dimension={len(result.vector)}")
        print(f"norma={norm:.6f}")
        print(f"lotes={result.statistics.batch_count}")
        print(f"entradas={result.statistics.input_count}")
        print("EMBEDDING DE CONSULTA: OK")
    finally:
        await close_ollama_client()


if __name__ == "__main__":
    asyncio.run(main())
