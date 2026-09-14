import asyncio
from pathlib import Path

from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
    postgres_connection,
)
from catalina_ingestion.services.document_processing import (
    DocumentProcessingService,
)
from catalina_ingestion.services.extraction import (
    ExtractionService,
)


async def main() -> int:
    await open_postgres_pool()

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

        print(f"titulo={processed.title}")
        print(f"paginas={processed.page_count}")
        print(f"secciones={processed.section_count}")
        print(f"bloques={len(processed.blocks)}")
        print(f"chunks={len(processed.chunks)}")
        print(f"bloques_repetidos_eliminados={processed.removed_repeated_blocks}")
        print(f"hash_contenido={processed.content_sha256}")

        for chunk in processed.chunks:
            print(
                f"\nCHUNK {chunk.index}\n"
                f"pagina={chunk.page_start}-{chunk.page_end}\n"
                f"seccion={chunk.section!r}\n"
                f"tokens_estimados={chunk.estimated_tokens}\n"
                f"sha256={chunk.text_sha256}\n"
                f"texto={chunk.text!r}"
            )

        print("\nPROCESAMIENTO DOCUMENTAL: OK")
        return 0

    finally:
        await close_postgres_pool()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
