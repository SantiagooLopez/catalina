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

OLD_VERSION = "1.0.0"
NEW_VERSION = "2.0.0"

V2_CONTENT = (
    b"Documento de prueba tecnica del servicio de ingesta Catalina, "
    b"version dos.\n"
    b"Esta segunda version permite validar la actualizacion documental, "
    b"la reindexacion y el control de vigencia de la informacion.\n"
    b"Catalina debe recuperar exclusivamente esta version vigente y "
    b"no utilizar la version anterior reemplazada.\n"
)


async def create_v2_file():
    upload = UploadFile(
        filename="prueba_ingesta_catalina_v2.txt",
        file=BytesIO(V2_CONTENT),
    )

    return await StagingService().receive(upload)


async def get_versions():
    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                d.id,
                d.nombre,
                v.id,
                v.version,
                v.estado,
                v.ejecucion_indexacion_activa_id,
                e.estado
            FROM catalina.documentos AS d
            JOIN catalina.versiones_documentos AS v
                ON v.documento_id = d.id
            LEFT JOIN catalina.ejecuciones_indexacion AS e
                ON e.id = v.ejecucion_indexacion_activa_id
            WHERE d.codigo = %s
            ORDER BY v.id
            """,
            (DOCUMENT_CODE,),
        )

        return await cursor.fetchall()


async def get_pending_v2():
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
                NEW_VERSION,
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
            f"estado_version={row[4]} "
            f"run={row[5]} "
            f"estado_run={row[6]}"
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

        qdrant = get_qdrant_client()

        print()
        print("========================================")
        print("FASE 5.10 - PRUEBA DE REINDEXACION")
        print("========================================")

        before = await get_versions()

        print_versions(
            "===== ESTADO INICIAL =====",
            before,
        )

        old_rows = [row for row in before if row[3] == OLD_VERSION]

        if not old_rows:
            raise RuntimeError("No existe la version inicial 1.0.0.")

        old_version_id = old_rows[0][2]
        document_id = old_rows[0][0]

        existing_v2 = [row for row in before if row[3] == NEW_VERSION]

        if not existing_v2:
            print()
            print("===== REGISTRANDO V2 =====")

            validated_file = await create_v2_file()

            request = DocumentRegistrationRequest(
                codigo=DOCUMENT_CODE,
                nombre=("Prueba técnica del servicio de ingesta"),
                categoria="faq",
                version=NEW_VERSION,
                descripcion=(
                    "Segunda versión controlada para validar "
                    "reindexación y vigencia en la Fase 5.10."
                ),
                idioma="es",
                origen="prueba-interna",
                metadatos={
                    "tipo": "prueba_integracion",
                    "fase": "5.10",
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

        else:
            print()
            print("V2 ya existe. Se continuará con la validación de su estado.")

        versions_after_registration = await get_versions()

        print_versions(
            "===== ESTADO DESPUES DEL REGISTRO =====",
            versions_after_registration,
        )

        v2_rows = [row for row in versions_after_registration if row[3] == NEW_VERSION]

        if not v2_rows:
            raise RuntimeError("La version 2.0.0 no quedo registrada.")

        new_version_id = v2_rows[0][2]

        if v2_rows[0][4] != "activa":
            print()
            print("===== INDEXANDO V2 =====")

            row = await get_pending_v2()

            if row is None:
                raise RuntimeError(
                    "V2 existe pero no posee un trabajo pendiente que pueda indexarse."
                )

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

            print("Extrayendo contenido...")

            extracted = await ExtractionService().extract(
                Path(row[7]),
                row[8],
            )

            print("Procesando y fragmentando...")

            processed = DocumentProcessingService().process(extracted)

            print(f"chunks_generados={len(processed.chunks)}")

            print("Generando embeddings...")

            embedded = await EmbeddingService().generate(processed.chunks)

            print(f"modelo_embedding={embedded.model}")
            print(f"dimension_embedding={embedded.dimension}")

            print("Indexando en Qdrant...")

            indexing = await QdrantIndexingService().index(
                context,
                processed,
                embedded,
            )

            print()
            print("===== INDEXACION V2 COMPLETADA =====")
            print(f"ejecucion={indexing.index_run_id}")
            print(f"puntos={indexing.point_count}")
            print(f"estado={indexing.state}")

        after = await get_versions()

        print_versions(
            "===== ESTADO DESPUES DE REINDEXAR =====",
            after,
        )

        old_final = [row for row in after if row[3] == OLD_VERSION]

        new_final = [row for row in after if row[3] == NEW_VERSION]

        if len(old_final) != 1:
            raise RuntimeError("No se encontro exactamente una V1.")

        if len(new_final) != 1:
            raise RuntimeError("No se encontro exactamente una V2.")

        if old_final[0][4] != "reemplazada":
            raise RuntimeError("V1 debia quedar en estado reemplazada.")

        if new_final[0][4] != "activa":
            raise RuntimeError("V2 debia quedar en estado activa.")

        if new_final[0][5] is None:
            raise RuntimeError("V2 no posee ejecucion de indexacion activa.")

        print()
        print("Estados PostgreSQL: CORRECTOS")

        active_runs = await RetrievalRepository().active_runs(settings)

        print()
        print("===== EJECUCIONES AUTORIZADAS POR RETRIEVAL =====")

        for run_id, identity in active_runs.items():
            print(f"run={run_id} document_id={identity[0]} version_id={identity[1]}")

        old_authorized = any(identity[1] == old_version_id for identity in active_runs.values())

        if old_authorized:
            raise RuntimeError(
                "La version reemplazada V1 todavia esta autorizada por active_runs()."
            )

        new_authorized = any(identity[1] == new_version_id for identity in active_runs.values())

        if not new_authorized:
            raise RuntimeError("La nueva version V2 no aparece en active_runs().")

        print()
        print("Autorizacion de ejecuciones: CORRECTA")

        physical_points, _ = await qdrant.scroll(
            collection_name=(settings.qdrant_collection),
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(
                            value=document_id,
                        ),
                    )
                ]
            ),
            limit=100,
            with_payload=True,
            with_vectors=False,
        )

        print()
        print("===== PUNTOS FISICOS EN QDRANT =====")

        physical_versions = set()

        for point in physical_points:
            payload = point.payload or {}

            version = payload.get("version")

            physical_versions.add(version)

            print(f"point_id={point.id}")
            print(f"version={version}")
            print(f"document_version_id={payload.get('document_version_id')}")
            print(f"index_run_id={payload.get('index_run_id')}")
            print("---")

        if OLD_VERSION not in physical_versions:
            raise RuntimeError(
                "V1 ya no aparece fisicamente en Qdrant. "
                "La prueba esperaba conservarla para "
                "comprobar el aislamiento logico."
            )

        if NEW_VERSION not in physical_versions:
            raise RuntimeError("V2 no aparece fisicamente indexada en Qdrant.")

        print()
        print("Persistencia fisica V1 + V2: CORRECTA")

        print()
        print("===== PRUEBA DE RETRIEVAL =====")

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

        print(f"descartados_por_cambio={search.discarded_after_recheck}")

        for chunk in search.chunks:
            print()
            print(f"point_id={chunk.point_id}")
            print(f"version={chunk.version}")
            print(f"document_version_id={chunk.document_version_id}")
            print(f"score={chunk.score:.6f}")
            print(f"texto={chunk.text[:500]}")

        if not search.chunks:
            raise RuntimeError("Retrieval no devolvio la version activa.")

        leaked_v1 = any(chunk.document_version_id == old_version_id for chunk in search.chunks)

        if leaked_v1:
            raise RuntimeError("ERROR CRITICO: Retrieval devolvio V1 reemplazada.")

        wrong_version = any(chunk.document_version_id != new_version_id for chunk in search.chunks)

        if wrong_version:
            raise RuntimeError("Retrieval devolvio una version diferente de V2.")

        wrong_label = any(chunk.version != NEW_VERSION for chunk in search.chunks)

        if wrong_label:
            raise RuntimeError("Retrieval devolvio una etiqueta de version incorrecta.")

        print()
        print("========================================")
        print("FASE 5.10: REINDEXACION Y VIGENCIA OK")
        print("========================================")
        print("V1 permanece fisicamente en Qdrant, pero no es recuperable.")
        print("V2 es la unica version autorizada por el sistema de retrieval.")

        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
