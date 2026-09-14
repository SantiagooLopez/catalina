import asyncio
import sys

from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.clients.qdrant import (
    close_qdrant_client,
    open_qdrant_client,
)
from catalina_ingestion.core.config import get_settings
from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
    postgres_connection,
)


async def check_postgres() -> None:
    await open_postgres_pool()

    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                current_database(),
                current_user,
                EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'catalina'
                      AND table_name = 'trabajos_ingesta'
                )
            """
        )
        row = await cursor.fetchone()

    if row is None or row[2] is not True:
        raise RuntimeError("No se encontró catalina.trabajos_ingesta")

    print(f"PostgreSQL: OK (base={row[0]}, usuario={row[1]})")


async def check_qdrant() -> None:
    settings = get_settings()
    client = await open_qdrant_client()
    collection = await client.get_collection(settings.qdrant_collection)

    vector_size = collection.config.params.vectors.size

    if vector_size != settings.embedding_dimension:
        raise RuntimeError(
            f"Dimensión Qdrant={vector_size}, configuración={settings.embedding_dimension}"
        )

    print(f"Qdrant: OK (colección={settings.qdrant_collection}, dimensión={vector_size})")


async def check_ollama() -> None:
    settings = get_settings()
    client = await open_ollama_client()

    response = await client.post(
        "/api/embed",
        json={
            "model": settings.ollama_embedding_model,
            "input": "Prueba de conectividad del servicio Catalina",
        },
    )
    response.raise_for_status()

    embeddings = response.json().get("embeddings", [])

    if not embeddings:
        raise RuntimeError("Ollama no devolvió embeddings")

    dimension = len(embeddings[0])

    if dimension != settings.embedding_dimension:
        raise RuntimeError(
            f"Dimensión Ollama={dimension}, configuración={settings.embedding_dimension}"
        )

    print(f"Ollama: OK (modelo={settings.ollama_embedding_model}, dimensión={dimension})")


async def main() -> int:
    try:
        await check_postgres()
        await check_qdrant()
        await check_ollama()
    except Exception as error:
        print(
            f"ERROR: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1
    finally:
        await close_ollama_client()
        await close_qdrant_client()
        await close_postgres_pool()

    print("Todas las conexiones de Catalina funcionan correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
