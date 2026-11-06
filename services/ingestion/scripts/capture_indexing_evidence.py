"""Read-only evidence from the active PostgreSQL run and an exact Qdrant count."""

import argparse
import asyncio
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from qdrant_client import AsyncQdrantClient, models

from catalina_ingestion.core.config import get_settings


async def capture(document_code: str | None) -> dict:
    settings = get_settings()
    async with await AsyncConnection.connect(
        settings.database_conninfo, row_factory=dict_row,
    ) as connection:
        await connection.execute("SET TRANSACTION READ ONLY")
        cursor = await connection.execute(
            """
            SELECT d.codigo AS documento, v.id AS version_id, v.version,
                   e.id AS ejecucion_id, e.estado,
                   e.coleccion_qdrant AS coleccion,
                   e.modelo_embedding AS modelo, e.dimension_embedding AS dimension,
                   e.chunks_esperados AS esperados, e.chunks_indexados AS indexados,
                   e.fecha_activacion AS activacion, e.fecha_finalizacion AS finalizacion,
                   (SELECT COUNT(*) FROM catalina.fragmentos_documento f
                    WHERE f.ejecucion_indexacion_id = e.id) AS fragmentos_postgres
            FROM catalina.ejecuciones_indexacion e
            JOIN catalina.versiones_documentos v ON v.id = e.version_documento_id
            JOIN catalina.documentos d ON d.id = v.documento_id
            WHERE e.estado = 'activa' AND v.ejecucion_indexacion_activa_id = e.id
              AND (%s::text IS NULL OR d.codigo = %s)
            ORDER BY e.fecha_activacion DESC NULLS LAST, e.fecha_creacion DESC
            LIMIT 1
            """,
            (document_code, document_code),
        )
        row = await cursor.fetchone()
    if row is None:
        raise RuntimeError("No se encontro una ejecucion activa para esa seleccion.")

    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url, timeout=settings.qdrant_timeout_seconds,
    )
    try:
        info = await qdrant.get_collection(row["coleccion"])
        vectors = info.config.params.vectors
        dimensions = (
            {name: params.size for name, params in vectors.items()}
            if isinstance(vectors, dict) else {"default": vectors.size}
        )
        count = await qdrant.count(
            collection_name=row["coleccion"], exact=True,
            count_filter=models.Filter(must=[models.FieldCondition(
                key="index_run_id",
                match=models.MatchValue(value=str(row["ejecucion_id"])),
            )]),
        )
    finally:
        await qdrant.close()
    return {
        "captura_utc": datetime.now(UTC).isoformat(), "servidor": socket.gethostname(),
        **row, "dimensiones_qdrant": dimensions, "puntos_qdrant_ejecucion": count.count,
        "conteos_coinciden": (
            row["esperados"] == row["indexados"] == row["fragmentos_postgres"] == count.count
        ),
        "dimension_coincide": bool(dimensions) and all(
            value == row["dimension"] for value in dimensions.values()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--document-code", help="Codigo del documento; omitir para el ultimo activo",
    )
    parser.add_argument("--output", type=Path, help="Guardar tambien los datos reales en JSON")
    args = parser.parse_args()
    result = asyncio.run(capture(args.document_code))
    print("CATALINA | EVIDENCIA REAL DE INDEXACION")
    print("Origen: PostgreSQL + Qdrant. Consulta de solo lectura.")
    for label, key in (
        ("Fecha UTC", "captura_utc"), ("Servidor", "servidor"), ("Documento", "documento"),
        ("ID version", "version_id"), ("Version", "version"),
        ("ID ejecucion", "ejecucion_id"), ("Estado ejecucion", "estado"),
        ("Coleccion", "coleccion"), ("Modelo embedding registrado", "modelo"),
        ("Dimension registrada", "dimension"), ("Dimension real Qdrant", "dimensiones_qdrant"),
        ("Fragmentos esperados", "esperados"), ("Fragmentos indexados", "indexados"),
        ("Fragmentos en PostgreSQL", "fragmentos_postgres"),
        ("Puntos reales Qdrant / ejecucion", "puntos_qdrant_ejecucion"),
        ("Conteos coinciden", "conteos_coinciden"), ("Dimension coincide", "dimension_coincide"),
        ("Fecha activacion", "activacion"), ("Fecha finalizacion", "finalizacion"),
    ):
        print(f"{label:34}: {result[key]}")
    print("Activa = indice publicado y disponible; no significa un proceso trabajando ahora.")
    if args.output:
        args.output.write_text(
            json.dumps(result, default=str, ensure_ascii=False, indent=2), "utf-8",
        )
        print(f"Datos guardados en: {args.output}")


if __name__ == "__main__":
    main()
