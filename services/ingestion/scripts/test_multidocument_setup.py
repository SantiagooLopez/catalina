import asyncio
from contextlib import AsyncExitStack
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

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
    postgres_connection,
)
from catalina_ingestion.domain.indexing import IndexingContext
from catalina_ingestion.schemas.documents import (
    DocumentRegistrationRequest,
)
from catalina_ingestion.services.document_processing import (
    DocumentProcessingService,
)
from catalina_ingestion.services.document_registration import (
    DocumentRegistrationService,
)
from catalina_ingestion.services.embeddings import EmbeddingService
from catalina_ingestion.services.extraction import ExtractionService
from catalina_ingestion.services.qdrant_indexing import (
    QdrantIndexingService,
)
from catalina_ingestion.services.staging import StagingService

DOCUMENT_CODE = "prueba-recuperacion-multidocumento"
DOCUMENT_VERSION = "1.0.0"

DOCUMENT_CONTENT = (
    b"Documento secundario de prueba del sistema Catalina.\n"
    b"Este documento permite validar busquedas sobre multiples documentos "
    b"activos y comprobar el funcionamiento de filtros independientes.\n"
    b"La palabra de control exclusiva de este documento es MULTICATALINA511.\n"
)


async def create_file():
    upload = UploadFile(
        filename="prueba_multidocumento_catalina.txt",
        file=BytesIO(DOCUMENT_CONTENT),
    )

    return await StagingService().receive(upload)


async def get_document():
    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                d.id,
                d.nombre,
                d.categoria,
                d.idioma,
                d.metadatos,
                v.id,
                v.version,
                v.estado,
                v.ruta_archivo,
                v.extension,
                v.nombre_archivo_original,
                t.id,
                t.estado
            FROM catalina.documentos AS d
            JOIN catalina.versiones_documentos AS v
                ON v.documento_id = d.id
            JOIN catalina.trabajos_ingesta AS t
                ON t.version_documento_id = v.id
            WHERE d.codigo = %s
              AND v.version = %s
            ORDER BY t.fecha_creacion DESC
            LIMIT 1
            """,
            (
                DOCUMENT_CODE,
                DOCUMENT_VERSION,
            ),
        )

        return await cursor.fetchone()


async def main() -> int:
    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        row = await get_document()

        if row is None:
            print("===== REGISTRANDO SEGUNDO DOCUMENTO =====")

            validated_file = await create_file()

            request = DocumentRegistrationRequest(
                codigo=DOCUMENT_CODE,
                nombre="Documento secundario de recuperación Catalina",
                categoria="faq",
                version=DOCUMENT_VERSION,
                descripcion=("Documento controlado para pruebas multidocumento de la Fase 5.11."),
                idioma="es",
                origen="prueba-interna",
                metadatos={
                    "tipo": "prueba_multidocumento",
                    "fase": "5.11",
                },
            )

            registration = await DocumentRegistrationService().register(
                validated_file,
                request,
            )

            print(
                registration.model_dump_json(
                    indent=2,
                )
            )

            row = await get_document()

        if row is None:
            raise RuntimeError("No se encontró el segundo documento.")

        print()
        print("===== DOCUMENTO ENCONTRADO =====")
        print(f"document_id={row[0]}")
        print(f"version_id={row[5]}")
        print(f"version={row[6]}")
        print(f"estado_version={row[7]}")
        print(f"estado_trabajo={row[12]}")

        if row[7] == "activa":
            print()
            print("El segundo documento ya se encuentra activo.")
            return 0

        if row[12] != "pendiente":
            raise RuntimeError("El trabajo del segundo documento no está pendiente.")

        context = IndexingContext(
            document_id=row[0],
            document_version_id=row[5],
            ingestion_job_id=row[11],
            document_name=row[1],
            version=row[6],
            category=row[2],
            language=row[3],
            source_file=row[10],
            metadata=row[4] or {},
        )

        print()
        print("===== INDEXANDO SEGUNDO DOCUMENTO =====")

        extracted = await ExtractionService().extract(
            Path(row[8]),
            row[9],
        )

        processed = DocumentProcessingService().process(extracted)

        print(f"chunks_generados={len(processed.chunks)}")

        embedded = await EmbeddingService().generate(processed.chunks)

        print(f"modelo={embedded.model}")
        print(f"dimension={embedded.dimension}")

        indexing = await QdrantIndexingService().index(
            context,
            processed,
            embedded,
        )

        print()
        print("===== INDEXACION COMPLETADA =====")
        print(f"run={indexing.index_run_id}")
        print(f"puntos={indexing.point_count}")
        print(f"estado={indexing.state}")

        final_row = await get_document()

        if final_row is None:
            raise RuntimeError("El documento desapareció después de indexar.")

        print()
        print("===== ESTADO FINAL =====")
        print(f"document_id={final_row[0]}")
        print(f"version_id={final_row[5]}")
        print(f"version={final_row[6]}")
        print(f"estado_version={final_row[7]}")
        print(f"estado_trabajo={final_row[12]}")

        if final_row[7] != "activa":
            raise RuntimeError("El segundo documento no quedó activo.")

        if final_row[12] != "completado":
            raise RuntimeError("El trabajo de ingesta no quedó completado.")

        print()
        print("========================================")
        print("FASE 5.11.4: SEGUNDO DOCUMENTO OK")
        print("========================================")

        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
