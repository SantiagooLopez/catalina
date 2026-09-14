import asyncio
import math
from pathlib import Path

from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
    postgres_connection,
)
from catalina_ingestion.services.document_processing import (
    DocumentProcessingService,
)
from catalina_ingestion.services.embeddings import (
    EmbeddingService,
)
from catalina_ingestion.services.extraction import (
    ExtractionService,
)


async def main() -> int:
    await open_postgres_pool()
    await open_ollama_client()

    try:
        async with postgres_connection() as connection:
            cursor = await connection.execute(
                """
                SELECT v.ruta_archivo, v.extension
                FROM catalina.versiones_documentos v
                JOIN catalina.documentos d
                  ON d.id = v.documento_id
                WHERE d.codigo = 'prueba-tecnica-ingesta'
                  AND v.version = '1.0.0'
                """
            )
            row = await cursor.fetchone()

        if row is None:
            print("No se encontró el documento de prueba.")
            return 1

        extracted = await ExtractionService().extract(
            Path(row[0]),
            row[1],
        )

        processed = DocumentProcessingService().process(extracted)

        embedded = await EmbeddingService().generate(processed.chunks)

        print(f"modelo={embedded.model}")
        print(f"dimension={embedded.dimension}")
        print(f"chunks={len(embedded.chunks)}")
        print(f"lotes={embedded.statistics.batch_count}")
        print(f"tokens_evaluados={embedded.statistics.prompt_eval_count}")
        print(f"duracion_segundos={embedded.statistics.total_duration_ns / 1_000_000_000:.3f}")

        for item in embedded.chunks:
            norm = math.sqrt(sum(value * value for value in item.vector))

            print(
                f"chunk={item.chunk.index} "
                f"vector_dimension={len(item.vector)} "
                f"norma={norm:.6f} "
                f"primeros_valores={item.vector[:5]}"
            )

        print("GENERACIÓN REAL DE EMBEDDINGS: OK")
        return 0

    finally:
        await close_ollama_client()
        await close_postgres_pool()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
