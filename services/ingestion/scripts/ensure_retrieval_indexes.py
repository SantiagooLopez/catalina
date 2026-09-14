import asyncio

from qdrant_client import models

from catalina_ingestion.clients.qdrant import (
    close_qdrant_client,
    open_qdrant_client,
)
from catalina_ingestion.core.config import get_settings


async def main():
    settings = get_settings()

    expected = {
        "index_run_id": models.PayloadSchemaType.KEYWORD,
        "embedding_model": models.PayloadSchemaType.KEYWORD,
        "document_id": models.PayloadSchemaType.INTEGER,
        "document_version_id": models.PayloadSchemaType.INTEGER,
        "category": models.PayloadSchemaType.KEYWORD,
        "language": models.PayloadSchemaType.KEYWORD,
        "version": models.PayloadSchemaType.KEYWORD,
        "section": models.PayloadSchemaType.KEYWORD,
        "page_start": models.PayloadSchemaType.INTEGER,
        "page_end": models.PayloadSchemaType.INTEGER,
    }

    try:
        client = await open_qdrant_client()
        info = await client.get_collection(settings.qdrant_collection)

        # Comprueba todos los existentes antes de crear alguno.
        for name, kind in expected.items():
            existing = info.payload_schema.get(name)
            if existing is not None and existing.data_type != kind:
                raise RuntimeError(
                    f"Índice incompatible: {name}; actual={existing.data_type}, esperado={kind}"
                )

        for name, kind in expected.items():
            if name not in info.payload_schema:
                await client.create_payload_index(
                    collection_name=settings.qdrant_collection,
                    field_name=name,
                    field_schema=kind,
                    wait=True,
                )
                print(f"creado={name}")
            else:
                print(f"existente={name}")

        updated = await client.get_collection(settings.qdrant_collection)
        for name, kind in expected.items():
            index = updated.payload_schema.get(name)
            if index is None or index.data_type != kind:
                raise RuntimeError(f"No se pudo verificar {name}.")

        print("ÍNDICES DE FILTRADO: OK")
    finally:
        await close_qdrant_client()


if __name__ == "__main__":
    asyncio.run(main())
