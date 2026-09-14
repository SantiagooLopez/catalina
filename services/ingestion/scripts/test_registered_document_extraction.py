import asyncio
from pathlib import Path

from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
    postgres_connection,
)
from catalina_ingestion.services.extraction import ExtractionService


async def main() -> int:
    await open_postgres_pool()

    try:
        async with postgres_connection() as connection:
            cursor = await connection.execute(
                """
                SELECT
                    v.ruta_archivo,
                    v.extension
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

        result = await ExtractionService().extract(
            Path(row[0]),
            row[1],
        )

        print(f"titulo={result.title}")
        print(f"paginas={result.page_count}")
        print(f"secciones={result.section_count}")
        print(f"bloques={len(result.blocks)}")

        for block in result.blocks:
            print(
                f"[{block.index}] "
                f"tipo={block.block_type} "
                f"pagina={block.page_number} "
                f"seccion={block.section!r} "
                f"texto={block.text!r}"
            )

        print("EXTRACCIÓN DEL DOCUMENTO REGISTRADO: OK")
        return 0

    finally:
        await close_postgres_pool()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
