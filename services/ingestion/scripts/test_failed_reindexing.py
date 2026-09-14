import asyncio
from contextlib import AsyncExitStack
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
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
from catalina_ingestion.domain.exceptions import IndexingError
from catalina_ingestion.domain.indexing import IndexingContext
from catalina_ingestion.domain.retrieval import (
    RetrievalFilter,
    RetrievalQuery,
)
from catalina_ingestion.repositories.retrieval import (
    RetrievalRepository,
)
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
from catalina_ingestion.services.vector_search import (
    VectorSearchService,
)

DOCUMENT_CODE = "prueba-tecnica-ingesta"

VALID_VERSION = "2.0.0"
FAILED_VERSION = "3.0.0"

V3_CONTENT = (
    b"Documento de prueba tecnica del servicio de ingesta Catalina, "
    b"version tres.\n"
    b"Esta version se utiliza exclusivamente para validar el rollback "
    b"de una reindexacion fallida.\n"
    b"El fallo controlado debe impedir que esta version reemplace "
    b"la version dos actualmente vigente.\n"
)


class FailAfterUpsertClient:
    """
    Cliente envoltorio para provocar un fallo controlado.

    Permite que Qdrant reciba los puntos de V3, pero falla cuando
    QdrantIndexingService intenta contar/verificar esos puntos.

    El servicio real debe entonces ejecutar su rollback.
    """

    def __init__(self, inner):
        self.inner = inner
        self.upsert_completed = False
        self.delete_called = False
        self.run_id = None
        self.points_after_upsert = 0

    async def upsert(self, **kwargs):
        result = await self.inner.upsert(**kwargs)

        self.upsert_completed = True

        points = kwargs.get("points") or []

        if points:
            payload = points[0].payload or {}
            self.run_id = payload.get("index_run_id")

        if self.run_id is not None:
            verification = await self.inner.count(
                collection_name=kwargs["collection_name"],
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="index_run_id",
                            match=models.MatchValue(
                                value=self.run_id,
                            ),
                        )
                    ]
                ),
                exact=True,
            )

            self.points_after_upsert = verification.count

        return result

    async def count(self, **kwargs):
        if self.upsert_completed:
            raise RuntimeError("CONTROLLED_FAILURE_AFTER_UPSERT_5_11")

        return await self.inner.count(**kwargs)

    async def delete(self, **kwargs):
        self.delete_called = True
        return await self.inner.delete(**kwargs)


async def create_v3_file():
    upload = UploadFile(
        filename="prueba_ingesta_catalina_v3.txt",
        file=BytesIO(V3_CONTENT),
    )

    return await StagingService().receive(upload)


async def get_versions():
    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                d.id,
                d.codigo,
                v.id,
                v.version,
                v.estado,
                v.ejecucion_indexacion_activa_id
            FROM catalina.documentos AS d
            JOIN catalina.versiones_documentos AS v
                ON v.documento_id = d.id
            WHERE d.codigo = %s
            ORDER BY v.id
            """,
            (DOCUMENT_CODE,),
        )

        return await cursor.fetchall()


async def get_executions():
    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                e.id,
                v.id,
                v.version,
                e.estado,
                e.error_codigo,
                e.chunks_esperados,
                e.chunks_indexados
            FROM catalina.ejecuciones_indexacion AS e
            JOIN catalina.versiones_documentos AS v
                ON v.id = e.version_documento_id
            JOIN catalina.documentos AS d
                ON d.id = v.documento_id
            WHERE d.codigo = %s
            ORDER BY e.fecha_creacion, e.id
            """,
            (DOCUMENT_CODE,),
        )

        return await cursor.fetchall()


async def get_pending_v3():
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
            FROM catalina.documentos AS d
            JOIN catalina.versiones_documentos AS v
                ON v.documento_id = d.id
            JOIN catalina.trabajos_ingesta AS t
                ON t.version_documento_id = v.id
            WHERE d.codigo = %s
              AND v.version = %s
              AND t.estado = 'pendiente'
            ORDER BY t.fecha_creacion DESC
            LIMIT 1
            """,
            (
                DOCUMENT_CODE,
                FAILED_VERSION,
            ),
        )

        return await cursor.fetchone()


def print_versions(title, rows):
    print()
    print(title)

    for row in rows:
        print(
            f"documento_id={row[0]} "
            f"version_id={row[2]} "
            f"version={row[3]} "
            f"estado={row[4]} "
            f"run_activo={row[5]}"
        )


def print_executions(rows):
    print()
    print("===== EJECUCIONES DE INDEXACION =====")

    for row in rows:
        print(
            f"run={row[0]} "
            f"version_id={row[1]} "
            f"version={row[2]} "
            f"estado={row[3]} "
            f"error={row[4]} "
            f"esperados={row[5]} "
            f"indexados={row[6]}"
        )


async def main() -> int:
    settings = get_settings()

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        real_qdrant = get_qdrant_client()

        print()
        print("========================================")
        print("FASE 5.11 - REINDEXACION FALLIDA")
        print("========================================")

        before = await get_versions()

        print_versions(
            "===== ESTADO INICIAL =====",
            before,
        )

        v2_before = [row for row in before if row[3] == VALID_VERSION]

        if len(v2_before) != 1:
            raise RuntimeError("No se encontro exactamente una V2.")

        if v2_before[0][4] != "activa":
            raise RuntimeError("V2 debe estar activa antes de iniciar 5.11.")

        valid_version_id = v2_before[0][2]
        document_id = v2_before[0][0]

        existing_v3 = [row for row in before if row[3] == FAILED_VERSION]

        if not existing_v3:
            print()
            print("===== REGISTRANDO V3 =====")

            validated_file = await create_v3_file()

            request = DocumentRegistrationRequest(
                codigo=DOCUMENT_CODE,
                nombre=("Prueba técnica del servicio de ingesta"),
                categoria="faq",
                version=FAILED_VERSION,
                descripcion=(
                    "Versión controlada para validar un fallo de reindexación en la Fase 5.11."
                ),
                idioma="es",
                origen="prueba-interna",
                metadatos={
                    "tipo": "prueba_integracion",
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

        after_registration = await get_versions()

        print_versions(
            "===== ESTADO DESPUES DEL REGISTRO =====",
            after_registration,
        )

        v3_rows = [row for row in after_registration if row[3] == FAILED_VERSION]

        if len(v3_rows) != 1:
            raise RuntimeError("No se encontro exactamente una V3.")

        failed_version_id = v3_rows[0][2]
        failed_state = v3_rows[0][4]

        if failed_state == "activa":
            raise RuntimeError("V3 ya aparece activa. Ese estado no es valido para esta prueba.")

        failure_client = None

        if failed_state != "fallida":
            row = await get_pending_v3()

            if row is None:
                raise RuntimeError("V3 no posee un trabajo pendiente.")

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

            print()
            print("===== PREPARANDO V3 =====")

            print("Extrayendo contenido...")

            extracted = await ExtractionService().extract(
                Path(row[7]),
                row[8],
            )

            print("Procesando contenido...")

            processed = DocumentProcessingService().process(extracted)

            print(f"chunks_generados={len(processed.chunks)}")

            print("Generando embeddings...")

            embedded = await EmbeddingService().generate(processed.chunks)

            print(f"modelo={embedded.model}")

            print(f"dimension={embedded.dimension}")

            failure_client = FailAfterUpsertClient(real_qdrant)

            service = QdrantIndexingService(client=failure_client)

            print()
            print("===== INICIANDO INDEXACION CON FALLO CONTROLADO =====")

            try:
                await service.index(
                    context,
                    processed,
                    embedded,
                )

            except IndexingError as error:
                print()
                print("FALLO CONTROLADO CAPTURADO")
                print(f"codigo={error.code}")
                print(f"mensaje={error.message}")

            else:
                raise RuntimeError("ERROR: V3 se indexo correctamente cuando debia fallar.")

            print()
            print("===== EVIDENCIA DEL FALLO =====")

            print(f"upsert_completado={failure_client.upsert_completed}")

            print(f"run_id={failure_client.run_id}")

            print(f"puntos_despues_del_upsert={failure_client.points_after_upsert}")

            print(f"rollback_delete_invocado={failure_client.delete_called}")

            if not failure_client.upsert_completed:
                raise RuntimeError("El fallo ocurrio antes del upsert.")

            if failure_client.points_after_upsert < 1:
                raise RuntimeError("No se comprobo que V3 hubiera entrado fisicamente en Qdrant.")

            if not failure_client.delete_called:
                raise RuntimeError("El rollback no intento borrar los puntos de V3.")

        else:
            print()
            print("V3 ya esta en estado fallida. Se continuara con las verificaciones.")

        after_failure = await get_versions()

        print_versions(
            "===== ESTADO DESPUES DEL FALLO =====",
            after_failure,
        )

        v2_after = [row for row in after_failure if row[3] == VALID_VERSION]

        v3_after = [row for row in after_failure if row[3] == FAILED_VERSION]

        if len(v2_after) != 1:
            raise RuntimeError("No se encontro V2 despues del fallo.")

        if len(v3_after) != 1:
            raise RuntimeError("No se encontro V3 despues del fallo.")

        if v2_after[0][4] != "activa":
            raise RuntimeError("ERROR CRITICO: V2 dejo de estar activa.")

        if v2_after[0][2] != valid_version_id:
            raise RuntimeError("Cambio inesperadamente la identidad de V2.")

        if v3_after[0][4] != "fallida":
            raise RuntimeError("V3 debia quedar en estado fallida.")

        if v3_after[0][5] is not None:
            raise RuntimeError("V3 no debe tener una ejecucion activa asociada.")

        print()
        print("Conservacion de V2: CORRECTA")

        executions = await get_executions()

        print_executions(executions)

        v3_executions = [row for row in executions if row[1] == failed_version_id]

        if not v3_executions:
            raise RuntimeError("No existe ejecucion registrada para V3.")

        latest_v3_execution = v3_executions[-1]

        if latest_v3_execution[3] != "fallida":
            raise RuntimeError("La ejecucion de V3 debia quedar fallida.")

        print()
        print("Estado de ejecucion V3: CORRECTO")

        active_runs = await RetrievalRepository().active_runs(settings)

        print()
        print("===== EJECUCIONES AUTORIZADAS POR RETRIEVAL =====")

        for run_id, identity in active_runs.items():
            print(f"run={run_id} document_id={identity[0]} version_id={identity[1]}")

        v2_authorized = any(identity[1] == valid_version_id for identity in active_runs.values())

        if not v2_authorized:
            raise RuntimeError("V2 dejo de estar autorizada por retrieval.")

        v3_authorized = any(identity[1] == failed_version_id for identity in active_runs.values())

        if v3_authorized:
            raise RuntimeError("ERROR CRITICO: V3 fallida esta autorizada por retrieval.")

        print()
        print("Autorizacion de retrieval: CORRECTA")

        v3_points, _ = await real_qdrant.scroll(
            collection_name=(settings.qdrant_collection),
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_version_id",
                        match=models.MatchValue(
                            value=failed_version_id,
                        ),
                    )
                ]
            ),
            limit=100,
            with_payload=True,
            with_vectors=False,
        )

        print()
        print("===== QDRANT DESPUES DEL ROLLBACK =====")

        print(f"puntos_v3={len(v3_points)}")

        for point in v3_points:
            print(f"point_id={point.id}")

        if v3_points:
            raise RuntimeError("ERROR CRITICO: quedaron puntos de V3 despues del rollback.")

        print()
        print("Limpieza de Qdrant: CORRECTA")

        print()
        print("===== COMPROBANDO RETRIEVAL V2 =====")

        search = await VectorSearchService().search(
            RetrievalQuery(
                query=("Que confirma la segunda version sobre la vigencia documental en Catalina?"),
                score_threshold=0.0,
                filters=RetrievalFilter(
                    document_id=document_id,
                ),
            )
        )

        print(f"candidatos={search.count}")

        for chunk in search.chunks:
            print()
            print(f"version={chunk.version}")
            print(f"document_version_id={chunk.document_version_id}")
            print(f"score={chunk.score:.6f}")
            print(f"texto={chunk.text[:500]}")

        if not search.chunks:
            raise RuntimeError("V2 ya no puede recuperarse.")

        if any(chunk.document_version_id != valid_version_id for chunk in search.chunks):
            raise RuntimeError("Retrieval devolvio una version distinta de V2.")

        if any(chunk.version != VALID_VERSION for chunk in search.chunks):
            raise RuntimeError("Retrieval no devolvio V2.")

        print()
        print("========================================")
        print("FASE 5.11.2: ROLLBACK DE REINDEXACION OK")
        print("========================================")
        print("V3 alcanzo Qdrant antes del fallo.")
        print("El rollback elimino los puntos de V3.")
        print("V3 quedo marcada como fallida.")
        print("V2 continuo activa y recuperable.")
        print("V3 no esta autorizada por retrieval.")

        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
