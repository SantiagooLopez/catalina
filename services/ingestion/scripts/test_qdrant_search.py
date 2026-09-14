import asyncio
import math

from qdrant_client import AsyncQdrantClient, models

from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.core.config import get_settings
from catalina_ingestion.services.embeddings import EmbeddingService
from catalina_ingestion.services.query_embedding import QueryEmbeddingService


async def main():
    settings = get_settings()
    collection = settings.qdrant_collection

    qdrant = AsyncQdrantClient(
       url="http://127.0.0.1:6333",
       timeout=30,
    )
    try:
        try:
            ollama = await open_ollama_client()
            service = QueryEmbeddingService(
                embedding_service=EmbeddingService(
                    settings=settings,
                    client=ollama,
                )
            )

            embedding = await service.generate(
                "¿Dónde puedo consultar el reglamento institucional?"
            )

            info = await qdrant.get_collection(collection)
            vectors = info.config.params.vectors

            if not isinstance(vectors, models.VectorParams):
                raise RuntimeError(
                    "La colección usa una configuración de vectores "
                    "distinta de la esperada; debemos revisarla."
                )

            if vectors.size != len(embedding.vector):
                raise RuntimeError(
                    f"Dimensiones incompatibles: colección={vectors.size}, "
                    f"consulta={len(embedding.vector)}"
                )

            if vectors.distance != models.Distance.COSINE:
                raise RuntimeError(
                    "La colección no tiene configurada distancia Cosine."
                )

            result = await qdrant.query_points(
                collection_name=collection,
                query=list(embedding.vector),
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="embedding_model",
                            match=models.MatchValue(
                                value=embedding.model,
                            ),
                        )
                    ]
                ),
                limit=5,
                with_payload=True,
                with_vectors=False,
            )

            print(f"consulta={embedding.normalized_query}")
            print(f"modelo={embedding.model}")
            print(f"dimension={len(embedding.vector)}")
            print(f"candidatos={len(result.points)}")

            for position, point in enumerate(result.points, start=1):
                if not math.isfinite(point.score):
                    raise RuntimeError("Qdrant devolvió un score no finito.")

                payload = point.payload or {}

                print()
                print(f"resultado={position}")
                print(f"point_id={point.id}")
                print(f"score={point.score:.6f}")

                for key in (
                    "document_id",
                    "document_version_id",
                    "index_run_id",
                    "document_name",
                    "version",
                    "category",
                    "language",
                    "page_start",
                    "page_end",
                    "section",
                    "embedding_model",
                ):
                    print(f"{key}={payload.get(key)}")

                print(f"texto={str(payload.get('text', ''))[:600]}")
                print(f"campos_payload={sorted(payload)}")

            print()
            print("CONSULTA A QDRANT: OK")

            if not result.points:
                print(
                    "La consulta funcionó, pero no encontró puntos "
                    "que coincidan con el modelo solicitado."
                )
        finally:
            await close_ollama_client()
    finally:
        await qdrant.close()


asyncio.run(main())
