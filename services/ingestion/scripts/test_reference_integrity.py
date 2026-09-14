import asyncio
from contextlib import AsyncExitStack

from qdrant_client import models

from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.clients.qdrant import (
    close_qdrant_client,
    get_qdrant_client,
    open_qdrant_client,
)
from catalina_ingestion.core.config import get_settings
from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
    postgres_connection,
)
from catalina_ingestion.domain.retrieval import (
    RetrievalFilter,
    RetrievalQuery,
)
from catalina_ingestion.repositories.retrieval import (
    RetrievalRepository,
)
from catalina_ingestion.services.vector_search import (
    VectorSearchService,
)

PRIMARY_CODE = "prueba-tecnica-ingesta"
SECONDARY_CODE = "prueba-recuperacion-multidocumento"


async def get_active_documents():
    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                d.id,
                d.codigo,
                d.nombre,
                d.categoria,
                d.idioma,
                v.id,
                v.version,
                v.estado,
                v.ejecucion_indexacion_activa_id,
                e.estado
            FROM catalina.documentos AS d
            JOIN catalina.versiones_documentos AS v
                ON v.documento_id = d.id
            JOIN catalina.ejecuciones_indexacion AS e
                ON e.id = v.ejecucion_indexacion_activa_id
               AND e.version_documento_id = v.id
            WHERE d.estado = 'activo'
              AND v.estado = 'activa'
              AND e.estado = 'activa'
            ORDER BY d.id
            """
        )

        return await cursor.fetchall()


async def get_fragment(point_id):
    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                f.id,
                f.ejecucion_indexacion_id,
                f.version_documento_id,
                f.chunk_index,
                f.pagina_inicio,
                f.pagina_fin,
                f.seccion,
                v.documento_id,
                v.version,
                d.codigo,
                d.nombre
            FROM catalina.fragmentos_documento AS f
            JOIN catalina.versiones_documentos AS v
                ON v.id = f.version_documento_id
            JOIN catalina.documentos AS d
                ON d.id = v.documento_id
            WHERE f.id = %s
            """,
            (point_id,),
        )

        return await cursor.fetchone()


async def get_active_document_by_code(code):
    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                d.id,
                v.id,
                v.version,
                v.ejecucion_indexacion_activa_id
            FROM catalina.documentos AS d
            JOIN catalina.versiones_documentos AS v
                ON v.documento_id = d.id
            WHERE d.codigo = %s
              AND d.estado = 'activo'
              AND v.estado = 'activa'
            LIMIT 1
            """,
            (code,),
        )

        return await cursor.fetchone()


def require_payload_fields(payload, point_id):
    required = (
        "document_id",
        "document_version_id",
        "index_run_id",
        "chunk_index",
        "document_name",
        "version",
        "category",
        "language",
        "source_file",
        "page_start",
        "page_end",
        "text",
        "text_sha256",
        "content_sha256",
        "embedding_model",
    )

    missing = [field for field in required if field not in payload]

    if missing:
        raise RuntimeError(f"El punto {point_id} no contiene los campos obligatorios: {missing}")


async def validate_qdrant_point(
    point,
    expected_document_id,
    expected_version_id,
    expected_run_id,
):
    payload = point.payload or {}

    require_payload_fields(
        payload,
        point.id,
    )

    print()
    print(f"point_id={point.id}")
    print(f"document_id={payload['document_id']}")
    print(f"document_version_id={payload['document_version_id']}")
    print(f"index_run_id={payload['index_run_id']}")
    print(f"documento={payload['document_name']}")
    print(f"version={payload['version']}")
    print(f"source_file={payload['source_file']}")
    print(f"paginas={payload['page_start']}-{payload['page_end']}")
    print(f"seccion={payload.get('section')}")
    print(f"chunk_index={payload['chunk_index']}")

    if payload["document_id"] != expected_document_id:
        raise RuntimeError(f"El punto {point.id} tiene document_id incorrecto.")

    if payload["document_version_id"] != expected_version_id:
        raise RuntimeError(f"El punto {point.id} tiene document_version_id incorrecto.")

    if payload["index_run_id"] != expected_run_id:
        raise RuntimeError(f"El punto {point.id} tiene index_run_id incorrecto.")

    fragment = await get_fragment(str(point.id))

    if fragment is None:
        raise RuntimeError(f"El point_id {point.id} no existe en catalina.fragmentos_documento.")

    fragment_point_id = str(fragment[0])
    fragment_run_id = str(fragment[1])
    fragment_version_id = fragment[2]
    fragment_chunk_index = fragment[3]
    fragment_page_start = fragment[4]
    fragment_page_end = fragment[5]
    fragment_section = fragment[6]
    fragment_document_id = fragment[7]
    fragment_version = fragment[8]
    fragment_code = fragment[9]
    fragment_name = fragment[10]

    if fragment_point_id != str(point.id):
        raise RuntimeError("El point_id no coincide entre Qdrant y PostgreSQL.")

    if fragment_run_id != payload["index_run_id"]:
        raise RuntimeError("El index_run_id no coincide entre Qdrant y PostgreSQL.")

    if fragment_version_id != payload["document_version_id"]:
        raise RuntimeError("El version_id no coincide entre Qdrant y PostgreSQL.")

    if fragment_document_id != payload["document_id"]:
        raise RuntimeError("El document_id no coincide entre Qdrant y PostgreSQL.")

    if fragment_chunk_index != payload["chunk_index"]:
        raise RuntimeError("El chunk_index no coincide.")

    if fragment_page_start != payload["page_start"]:
        raise RuntimeError("La pagina inicial no coincide.")

    if fragment_page_end != payload["page_end"]:
        raise RuntimeError("La pagina final no coincide.")

    if fragment_section != payload.get("section"):
        raise RuntimeError("La seccion no coincide.")

    if fragment_version != payload["version"]:
        raise RuntimeError("La etiqueta de version no coincide.")

    if fragment_name != payload["document_name"]:
        raise RuntimeError("El nombre documental no coincide.")

    print(f"codigo_postgres={fragment_code}")

    print("trazabilidad_qdrant_postgres=OK")


async def validate_retrieval_result(
    service,
    document_id,
    version_id,
    run_id,
    question,
):
    result = await service.search(
        RetrievalQuery(
            query=question,
            score_threshold=0.0,
            filters=RetrievalFilter(
                document_id=document_id,
            ),
        )
    )

    if not result.chunks:
        raise RuntimeError(f"Retrieval no devolvio chunks para document_id={document_id}.")

    for chunk in result.chunks:
        print()
        print(f"retrieved_point_id={chunk.point_id}")
        print(f"retrieved_document_id={chunk.document_id}")
        print(f"retrieved_version_id={chunk.document_version_id}")
        print(f"retrieved_version={chunk.version}")
        print(f"retrieved_run={chunk.metadata.get('index_run_id')}")

        if chunk.document_id != document_id:
            raise RuntimeError("Retrieval devolvio document_id incorrecto.")

        if chunk.document_version_id != version_id:
            raise RuntimeError("Retrieval devolvio version_id incorrecto.")

        if chunk.metadata.get("index_run_id") != run_id:
            raise RuntimeError("Retrieval devolvio index_run_id incorrecto.")

        fragment = await get_fragment(chunk.point_id)

        if fragment is None:
            raise RuntimeError("El chunk recuperado no posee fragmento registrado.")

        if str(fragment[1]) != run_id:
            raise RuntimeError("El run del chunk recuperado no coincide con PostgreSQL.")

        if fragment[2] != version_id:
            raise RuntimeError("La version del chunk recuperado no coincide con PostgreSQL.")

        if fragment[7] != document_id:
            raise RuntimeError("El documento del chunk recuperado no coincide con PostgreSQL.")

    print("trazabilidad_retrieval=OK")


async def main() -> int:
    settings = get_settings()

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        qdrant = get_qdrant_client()

        print()
        print("========================================")
        print("FASE 5.11.6 - INTEGRIDAD Y TRAZABILIDAD")
        print("========================================")

        active_documents = await get_active_documents()

        print()
        print("===== VERSIONES ACTIVAS =====")

        for row in active_documents:
            print(
                f"document_id={row[0]} "
                f"codigo={row[1]} "
                f"version_id={row[5]} "
                f"version={row[6]} "
                f"run={row[8]}"
            )

        if len(active_documents) < 2:
            raise RuntimeError("La prueba requiere al menos dos documentos activos.")

        active_runs = await RetrievalRepository().active_runs(settings)

        print()
        print("===== ACTIVE RUNS AUTORIZADOS =====")

        for run_id, identity in active_runs.items():
            print(f"run={run_id} document_id={identity[0]} version_id={identity[1]}")

        if len(active_runs) < 2:
            raise RuntimeError("Retrieval deberia tener al menos dos ejecuciones autorizadas.")

        print()
        print("===== AUDITORIA QDRANT -> POSTGRESQL =====")

        total_points = 0

        for run_id, identity in active_runs.items():
            document_id = identity[0]
            version_id = identity[1]

            points, _ = await qdrant.scroll(
                collection_name=(settings.qdrant_collection),
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="index_run_id",
                            match=models.MatchValue(
                                value=run_id,
                            ),
                        )
                    ]
                ),
                limit=100,
                with_payload=True,
                with_vectors=False,
            )

            print()
            print(f"RUN {run_id}")
            print(f"puntos={len(points)}")

            if not points:
                raise RuntimeError(f"La ejecucion {run_id} esta autorizada pero no posee puntos.")

            for point in points:
                await validate_qdrant_point(
                    point,
                    document_id,
                    version_id,
                    run_id,
                )

                total_points += 1

        print()
        print("===== RESUMEN AUDITORIA =====")
        print(f"puntos_activos_validados={total_points}")

        if total_points < 2:
            raise RuntimeError("Se esperaban al menos dos puntos activos.")

        primary = await get_active_document_by_code(PRIMARY_CODE)

        secondary = await get_active_document_by_code(SECONDARY_CODE)

        if primary is None:
            raise RuntimeError("No existe el documento principal activo.")

        if secondary is None:
            raise RuntimeError("No existe el documento secundario activo.")

        service = VectorSearchService()

        print()
        print("===== TRAZABILIDAD DESDE RETRIEVAL =====")

        print()
        print("--- DOCUMENTO PRINCIPAL ---")

        await validate_retrieval_result(
            service=service,
            document_id=primary[0],
            version_id=primary[1],
            run_id=str(primary[3]),
            question=("Que confirma la segunda version sobre la vigencia documental en Catalina?"),
        )

        print()
        print("--- DOCUMENTO SECUNDARIO ---")

        await validate_retrieval_result(
            service=service,
            document_id=secondary[0],
            version_id=secondary[1],
            run_id=str(secondary[3]),
            question=("Cual es la palabra de control MULTICATALINA511?"),
        )

        print()
        print("========================================")
        print("FASE 5.11.6: INTEGRIDAD Y TRAZABILIDAD OK")
        print("========================================")
        print("point_id -> PostgreSQL: OK")
        print("index_run_id -> version: OK")
        print("version -> documento: OK")
        print("chunk -> paginas/seccion: OK")
        print("Qdrant -> PostgreSQL: OK")
        print("Retrieval -> PostgreSQL: OK")

        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
