import asyncio
from contextlib import AsyncExitStack

from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.clients.qdrant import (
    close_qdrant_client,
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


async def get_active_document(code):
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


def print_chunks(result):
    print(f"candidatos={result.count}")

    print(f"descartados_por_cambio={result.discarded_after_recheck}")

    for chunk in result.chunks:
        print()
        print(f"point_id={chunk.point_id}")
        print(f"document_id={chunk.document_id}")
        print(f"document_version_id={chunk.document_version_id}")
        print(f"documento={chunk.document_name}")
        print(f"version={chunk.version}")
        print(f"categoria={chunk.category}")
        print(f"idioma={chunk.language}")
        print(f"paginas={chunk.page_start}-{chunk.page_end}")
        print(f"score={chunk.score:.6f}")
        print(f"run={chunk.metadata.get('index_run_id')}")
        print(f"texto={chunk.text[:400]}")


async def main() -> int:
    settings = get_settings()

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        primary = await get_active_document(PRIMARY_CODE)

        secondary = await get_active_document(SECONDARY_CODE)

        if primary is None:
            raise RuntimeError("No se encontro el documento principal activo.")

        if secondary is None:
            raise RuntimeError("No se encontro el documento secundario activo.")

        primary_document_id = primary[0]
        primary_version_id = primary[5]
        primary_version = primary[6]

        secondary_document_id = secondary[0]
        secondary_version_id = secondary[5]
        secondary_version = secondary[6]

        print()
        print("========================================")
        print("FASE 5.11.5 - FILTROS MULTIDOCUMENTO")
        print("========================================")

        print()
        print("===== DOCUMENTOS ACTIVOS =====")

        print(
            f"PRINCIPAL: document_id="
            f"{primary_document_id} "
            f"version_id={primary_version_id} "
            f"version={primary_version}"
        )

        print(
            f"SECUNDARIO: document_id="
            f"{secondary_document_id} "
            f"version_id={secondary_version_id} "
            f"version={secondary_version}"
        )

        if primary_version != "2.0.0":
            raise RuntimeError("El documento principal debe tener V2 como version activa.")

        if secondary_version != "1.0.0":
            raise RuntimeError("El documento secundario debe tener V1 como version activa.")

        active_runs = await RetrievalRepository().active_runs(settings)

        print()
        print("===== ACTIVE RUNS =====")

        for run_id, identity in active_runs.items():
            print(f"run={run_id} document_id={identity[0]} version_id={identity[1]}")

        service = VectorSearchService()

        print()
        print("========================================")
        print("CASO 1 - FILTRO DOCUMENTO PRINCIPAL")
        print("========================================")

        result_primary = await service.search(
            RetrievalQuery(
                query=("Que confirma la segunda version sobre la vigencia documental en Catalina?"),
                score_threshold=0.0,
                filters=RetrievalFilter(
                    document_id=primary_document_id,
                    document_version_id=(primary_version_id),
                    version="2.0.0",
                    category="faq",
                    language="es",
                    page_from=1,
                    page_to=1,
                ),
            )
        )

        print_chunks(result_primary)

        if not result_primary.chunks:
            raise RuntimeError("El filtro del documento principal no devolvio resultados.")

        if any(chunk.document_id != primary_document_id for chunk in result_primary.chunks):
            raise RuntimeError("El filtro del documento principal devolvio otro documento.")

        if any(chunk.document_version_id != primary_version_id for chunk in result_primary.chunks):
            raise RuntimeError("Se recupero una version incorrecta del documento principal.")

        print()
        print("CASO 1: OK")

        print()
        print("========================================")
        print("CASO 2 - FILTRO DOCUMENTO SECUNDARIO")
        print("========================================")

        result_secondary = await service.search(
            RetrievalQuery(
                query=("Cual es la palabra de control exclusiva del documento secundario?"),
                score_threshold=0.0,
                filters=RetrievalFilter(
                    document_id=secondary_document_id,
                    document_version_id=(secondary_version_id),
                    version="1.0.0",
                    category="faq",
                    language="es",
                    page_from=1,
                    page_to=1,
                ),
            )
        )

        print_chunks(result_secondary)

        if not result_secondary.chunks:
            raise RuntimeError("El documento secundario no fue recuperado.")

        if any(chunk.document_id != secondary_document_id for chunk in result_secondary.chunks):
            raise RuntimeError("El filtro del documento secundario devolvio otro documento.")

        if not any("MULTICATALINA511" in chunk.text for chunk in result_secondary.chunks):
            raise RuntimeError("No se recupero la palabra de control MULTICATALINA511.")

        print()
        print("CASO 2: OK")

        print()
        print("========================================")
        print("CASO 3 - BUSQUEDA MULTIDOCUMENTO")
        print("========================================")

        result_multiple = await service.search(
            RetrievalQuery(
                query=(
                    "Documentos de prueba Catalina para "
                    "validar versionado recuperacion "
                    "y busquedas."
                ),
                score_threshold=0.0,
                filters=RetrievalFilter(
                    category="faq",
                    language="es",
                ),
            )
        )

        print_chunks(result_multiple)

        returned_documents = {chunk.document_id for chunk in result_multiple.chunks}

        if primary_document_id not in returned_documents:
            raise RuntimeError("La busqueda multidocumento no devolvio el documento principal.")

        if secondary_document_id not in returned_documents:
            raise RuntimeError("La busqueda multidocumento no devolvio el documento secundario.")

        print()
        print("CASO 3: OK")

        print()
        print("========================================")
        print("CASO 4 - VERSION REEMPLAZADA")
        print("========================================")

        result_old_version = await service.search(
            RetrievalQuery(
                query=("Documento de prueba tecnica del servicio de ingesta Catalina"),
                score_threshold=0.0,
                filters=RetrievalFilter(
                    document_id=primary_document_id,
                    version="1.0.0",
                ),
            )
        )

        print_chunks(result_old_version)

        if result_old_version.chunks:
            raise RuntimeError("ERROR CRITICO: la version reemplazada 1.0.0 fue recuperada.")

        print()
        print("CASO 4: OK")

        print()
        print("========================================")
        print("CASO 5 - IDENTIDAD INCOMPATIBLE")
        print("========================================")

        result_mismatch = await service.search(
            RetrievalQuery(
                query="Documento Catalina",
                score_threshold=0.0,
                filters=RetrievalFilter(
                    document_id=secondary_document_id,
                    document_version_id=(primary_version_id),
                ),
            )
        )

        print_chunks(result_mismatch)

        if result_mismatch.chunks:
            raise RuntimeError(
                "Un document_id fue combinado incorrectamente con una version de otro documento."
            )

        print()
        print("CASO 5: OK")

        print()
        print("========================================")
        print("CASO 6 - RANGO DE PAGINA INEXISTENTE")
        print("========================================")

        result_page = await service.search(
            RetrievalQuery(
                query="MULTICATALINA511",
                score_threshold=0.0,
                filters=RetrievalFilter(
                    document_id=secondary_document_id,
                    page_from=99,
                    page_to=99,
                ),
            )
        )

        print_chunks(result_page)

        if result_page.chunks:
            raise RuntimeError("El filtro de pagina devolvio contenido fuera del rango.")

        print()
        print("CASO 6: OK")

        print()
        print("========================================")
        print("FASE 5.11.5: FILTROS MULTIDOCUMENTO OK")
        print("========================================")

        print("Documento principal aislado: OK")
        print("Documento secundario aislado: OK")
        print("Busqueda sobre ambos documentos: OK")
        print("Version reemplazada bloqueada: OK")
        print("Identidades incompatibles bloqueadas: OK")
        print("Filtro de paginas: OK")

        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
