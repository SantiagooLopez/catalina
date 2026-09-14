import asyncio
from pathlib import Path

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
from catalina_ingestion.services.document_processing import (
    DocumentProcessingService,
)
from catalina_ingestion.services.embeddings import (
    EmbeddingService,
)
from catalina_ingestion.services.extraction import (
    ExtractionService,
)
from catalina_ingestion.services.qdrant_indexing import (
    QdrantIndexingService,
)


async def main() -> int:
    await open_postgres_pool()
    await open_ollama_client()
    await open_qdrant_client()

    try:
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
                    v.ruta_archivo,
                    v.extension,
                    v.nombre_archivo_original,
                    t.id
                FROM catalina.documentos d
                JOIN catalina.versiones_documentos v
                  ON v.documento_id = d.id
                JOIN catalina.trabajos_ingesta t
                  ON t.version_documento_id = v.id
                WHERE d.codigo = 'prueba-tecnica-ingesta'
                  AND v.version = '1.0.0'
                  AND t.estado = 'pendiente'
                ORDER BY t.fecha_creacion DESC
                LIMIT 1
                """
            )
            row = await cursor.fetchone()

        if row is None:
            print("No se encontró un trabajo pendiente. Es posible que ya haya sido indexado.")
            return 1

        context = IndexingContext(
            document_id=row[0],
            document_version_id=row[5],
            ingestion_job_id=row[10],
            document_name=row[1],
            version=row[6],
            category=row[2],
            language=row[3],
            source_file=row[9],
            metadata=row[4] or {},
        )

        extracted = await ExtractionService().extract(
            Path(row[7]),
            row[8],
        )

        processed = DocumentProcessingService().process(extracted)

        embedded = await EmbeddingService().generate(processed.chunks)

        result = await QdrantIndexingService().index(
            context,
            processed,
            embedded,
        )

        print(f"ejecucion={result.index_run_id}")
        print(f"coleccion={result.collection}")
        print(f"puntos={result.point_count}")
        print(f"estado={result.state}")
        print(f"ids={result.point_ids}")
        print("INDEXACIÓN COMPLETA: OK")
        return 0

    finally:
        await close_qdrant_client()
        await close_ollama_client()
        await close_postgres_pool()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
