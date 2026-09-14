import asyncio

from qdrant_client import models

from catalina_ingestion.clients.qdrant import (
    close_qdrant_client,
    open_qdrant_client,
)
from catalina_ingestion.core.config import get_settings


async def main() -> int:
    settings = get_settings()
    client = await open_qdrant_client()

    indexes = {
        "document_id": models.PayloadSchemaType.INTEGER,
        "document_version_id": models.PayloadSchemaType.INTEGER,
        "chunk_index": models.PayloadSchemaType.INTEGER,
        "index_run_id": models.PayloadSchemaType.KEYWORD,
        "category": models.PayloadSchemaType.KEYWORD,
        "version": models.PayloadSchemaType.KEYWORD,
        "language": models.PayloadSchemaType.KEYWORD,
        "embedding_model": models.PayloadSchemaType.KEYWORD,
        "content_sha256": models.PayloadSchemaType.KEYWORD,
        "text_sha256": models.PayloadSchemaType.KEYWORD,
        "indexed_at": models.PayloadSchemaType.DATETIME,
        "text": models.PayloadSchemaType.TEXT,
    }

    try:
        information = await client.get_collection(settings.qdrant_collection)
        existing = set(information.payload_schema or {})

        for field_name, field_schema in indexes.items():
            if field_name in existing:
                print(f"{field_name}: ya existe")
                continue

            await client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field_name,
                field_schema=field_schema,
                wait=True,
            )

            print(f"{field_name}: creado")

        print("ÍNDICES DE PAYLOAD: OK")
        return 0
    finally:
        await close_qdrant_client()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
