import argparse
import asyncio
import json
from contextlib import AsyncExitStack
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
from catalina_ingestion.core.config import get_settings
from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
    postgres_connection,
)
from catalina_ingestion.domain.indexing import IndexingContext
from catalina_ingestion.repositories.retrieval import RetrievalRepository
from catalina_ingestion.schemas.documents import DocumentRegistrationRequest
from catalina_ingestion.services.document_processing import (
    DocumentProcessingService,
)
from catalina_ingestion.services.document_registration import (
    DocumentRegistrationService,
)
from catalina_ingestion.services.embeddings import EmbeddingService
from catalina_ingestion.services.extraction import ExtractionService
from catalina_ingestion.services.qdrant_indexing import QdrantIndexingService
from catalina_ingestion.services.staging import StagingService

ROOT = Path(__file__).resolve().parents[1]

CORPUS_DIRECTORY = ROOT / "evaluation" / "corpus"
MANIFEST_PATH = CORPUS_DIRECTORY / "manifest.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description=("Ingesta el corpus institucional de evaluación de Catalina.")
    )

    parser.add_argument(
        "--only",
        help=("Procesa únicamente un corpus_id, por ejemplo DOC001."),
    )

    return parser.parse_args()


def load_manifest():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    documents = manifest.get("documents")

    if not isinstance(documents, list):
        raise RuntimeError("manifest.json no contiene una lista válida en 'documents'.")

    if not documents:
        raise RuntimeError("El corpus está vacío.")

    return manifest, documents


def validate_manifest(documents, settings):
    print()
    print("========================================")
    print(" PREVALIDACION DEL CORPUS")
    print("========================================")

    required_fields = (
        "corpus_id",
        "code",
        "name",
        "version",
        "category",
        "source_type",
        "local_file",
        "status",
    )

    corpus_ids = set()
    codes = set()
    problems = []

    for document in documents:
        missing = [field for field in required_fields if field not in document]

        if missing:
            problems.append(f"{document.get('corpus_id', '?')}: campos faltantes={missing}")
            continue

        corpus_id = document["corpus_id"]
        code = document["code"]
        category = document["category"]
        status = document["status"]

        source_path = CORPUS_DIRECTORY / document["local_file"]

        if corpus_id in corpus_ids:
            problems.append(f"{corpus_id}: corpus_id duplicado")

        corpus_ids.add(corpus_id)

        if code in codes:
            problems.append(f"{corpus_id}: code duplicado={code}")

        codes.add(code)

        if category not in settings.allowed_categories:
            problems.append(f"{corpus_id}: categoria no permitida={category}")

        if status != "ready":
            problems.append(f"{corpus_id}: status={status}, se esperaba ready")

        if not source_path.is_file():
            problems.append(f"{corpus_id}: archivo inexistente={source_path}")

        print(
            f"{corpus_id} | "
            f"{code} | "
            f"version={document['version']} | "
            f"categoria={category} | "
            f"archivo={source_path.exists()}"
        )

    print()

    if problems:
        print("PREVALIDACION: FALLIDA")

        for problem in problems:
            print(f"- {problem}")

        raise RuntimeError("El corpus no superó la prevalidación.")

    print(f"documentos_validados={len(documents)}")
    print("PREVALIDACION: OK")


async def get_version(code, version):
    async with postgres_connection() as connection:
        cursor = await connection.execute(
            """
            SELECT
                d.id,
                d.codigo,
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
                v.ejecucion_indexacion_activa_id,
                t.id,
                t.estado
            FROM catalina.documentos AS d
            JOIN catalina.versiones_documentos AS v
                ON v.documento_id = d.id
            LEFT JOIN catalina.trabajos_ingesta AS t
                ON t.version_documento_id = v.id
            WHERE d.codigo = %s
              AND v.version = %s
            ORDER BY t.fecha_creacion DESC NULLS LAST
            LIMIT 1
            """,
            (
                code,
                version,
            ),
        )

        return await cursor.fetchone()


async def register_document(document):
    source_path = CORPUS_DIRECTORY / document["local_file"]

    print("Registrando documento...")

    file_handle = source_path.open("rb")

    upload = UploadFile(
        filename=source_path.name,
        file=file_handle,
    )

    validated_file = await StagingService().receive(upload)

    request = DocumentRegistrationRequest(
        codigo=document["code"],
        nombre=document["name"],
        categoria=document["category"],
        version=document["version"],
        descripcion=(
            "Fuente institucional controlada para la evaluación del sistema RAG Catalina."
        ),
        idioma="es",
        origen=("Universidad Católica de Colombia - corpus de evaluación 2026"),
        metadatos={
            "corpus_id": document["corpus_id"],
            "source_type": document["source_type"],
            "evaluation_corpus": True,
            "evaluation_period": "2026",
            "source_local_file": document["local_file"],
        },
    )

    result = await DocumentRegistrationService().register(
        validated_file,
        request,
    )

    print(f"document_id={result.document_id}")
    print(f"document_version_id={result.document_version_id}")
    print(f"job_id={result.ingestion_job_id}")
    print(f"estado={result.estado}")

    return result


async def prepare_and_index(document, row):
    document_id = row[0]
    document_name = row[2]
    category = row[3]
    language = row[4]
    metadata = row[5] or {}

    version_id = row[6]
    version = row[7]
    version_state = row[8]

    storage_path = row[9]
    extension = row[10]
    original_name = row[11]

    ingestion_job_id = row[13]
    ingestion_job_state = row[14]

    if version_state != "pendiente":
        raise RuntimeError(f"La versión {version} no está pendiente. estado={version_state}")

    if ingestion_job_id is None:
        raise RuntimeError("La versión pendiente no posee trabajo de ingesta.")

    if ingestion_job_state != "pendiente":
        raise RuntimeError(f"El trabajo de ingesta no está pendiente. estado={ingestion_job_state}")

    if storage_path is None:
        raise RuntimeError("La versión pendiente no posee ruta de almacenamiento.")

    path = Path(storage_path)

    if not path.is_file():
        raise RuntimeError(f"El archivo persistido no existe: {path}")

    context = IndexingContext(
        document_id=document_id,
        document_version_id=version_id,
        ingestion_job_id=ingestion_job_id,
        document_name=document_name,
        version=version,
        category=category,
        language=language,
        source_file=original_name,
        metadata=metadata,
    )

    print("Extrayendo contenido...")

    extracted = await ExtractionService().extract(
        path,
        extension,
    )

    print(f"paginas_extraidas={extracted.page_count}")

    print("Procesando y fragmentando...")

    processed = DocumentProcessingService().process(extracted)

    print(f"chunks_generados={len(processed.chunks)}")

    if not processed.chunks:
        raise RuntimeError("El documento no generó chunks.")

    print("Generando embeddings...")

    embedded = await EmbeddingService().generate(processed.chunks)

    print(f"modelo_embedding={embedded.model}")
    print(f"dimension_embedding={embedded.dimension}")

    print("Indexando en Qdrant...")

    result = await QdrantIndexingService().index(
        context,
        processed,
        embedded,
    )

    print(f"index_run_id={result.index_run_id}")
    print(f"puntos_indexados={result.point_count}")
    print(f"estado_indexacion={result.state}")

    return result


async def process_document(document):
    corpus_id = document["corpus_id"]
    code = document["code"]
    version = document["version"]

    print()
    print("========================================")
    print(f"{corpus_id} - {document['name']}")
    print("========================================")
    print(f"codigo={code}")
    print(f"version={version}")
    print(f"categoria={document['category']}")
    print(f"archivo={document['local_file']}")

    row = await get_version(
        code,
        version,
    )

    if row is not None:
        version_state = row[8]

        print(f"estado_existente={version_state}")

        if version_state == "activa":
            print("Resultado: OMITIDO (ya está activo)")

            return {
                "corpus_id": corpus_id,
                "status": "skipped_active",
                "document_id": row[0],
                "version_id": row[6],
            }

        if version_state == "fallida":
            raise RuntimeError(
                "La misma versión ya existe en estado fallida. No se reutilizará automáticamente."
            )

        if version_state == "reemplazada":
            raise RuntimeError(
                "La misma versión existe como "
                "reemplazada. Se requiere una nueva "
                "etiqueta de versión."
            )

        if version_state != "pendiente":
            raise RuntimeError(f"Estado de versión no reanudable: {version_state}")

        print("Versión pendiente encontrada. Se reanudará la ingesta.")

    else:
        await register_document(document)

        row = await get_version(
            code,
            version,
        )

        if row is None:
            raise RuntimeError(
                "El documento fue registrado pero no pudo recuperarse desde PostgreSQL."
            )

    indexing = await prepare_and_index(
        document,
        row,
    )

    final_row = await get_version(
        code,
        version,
    )

    if final_row is None:
        raise RuntimeError("No se encontró la versión después de completar la indexación.")

    final_state = final_row[8]
    active_run = final_row[12]
    final_job_state = final_row[14]

    print()
    print("===== VERIFICACION FINAL =====")
    print(f"document_id={final_row[0]}")
    print(f"version_id={final_row[6]}")
    print(f"estado_version={final_state}")
    print(f"run_activo={active_run}")
    print(f"estado_trabajo={final_job_state}")

    if final_state != "activa":
        raise RuntimeError("La versión no quedó activa.")

    if final_job_state != "completado":
        raise RuntimeError("El trabajo de ingesta no quedó completado.")

    if str(active_run) != str(indexing.index_run_id):
        raise RuntimeError("La ejecución activa no coincide con la indexación recién completada.")

    print("Resultado: ACTIVE ✅")

    return {
        "corpus_id": corpus_id,
        "status": "active",
        "document_id": final_row[0],
        "version_id": final_row[6],
    }


async def validate_retrieval_authorization(
    successful,
    settings,
):
    active_runs = await RetrievalRepository().active_runs(settings)

    print()
    print("========================================")
    print(" AUTORIZACION DE RETRIEVAL")
    print("========================================")

    for run_id, identity in active_runs.items():
        print(f"run={run_id} document_id={identity[0]} version_id={identity[1]}")

    authorized_identities = set(active_runs.values())

    for result in successful:
        if result["status"] not in {
            "active",
            "skipped_active",
        }:
            continue

        identity = (
            result["document_id"],
            result["version_id"],
        )

        if identity not in authorized_identities:
            raise RuntimeError(
                f"{result['corpus_id']} quedó activo pero no está autorizado por retrieval."
            )

    print()
    print("Documentos procesados autorizados por retrieval: OK")


async def main():
    args = parse_args()
    settings = get_settings()

    manifest, documents = load_manifest()

    validate_manifest(
        documents,
        settings,
    )

    selected = documents

    if args.only is not None:
        selected = [document for document in documents if document["corpus_id"] == args.only]

        if not selected:
            raise RuntimeError(f"No existe corpus_id={args.only}")

    print()
    print("========================================")
    print(" FASE 5.12.2 - INGESTA DEL CORPUS")
    print("========================================")
    print(f"corpus={manifest['name']}")
    print(f"documentos_seleccionados={len(selected)}")

    successful = []
    failures = []

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        for document in selected:
            try:
                result = await process_document(document)

                successful.append(result)

            except Exception as error:
                failures.append(
                    {
                        "corpus_id": (document["corpus_id"]),
                        "error_type": (type(error).__name__),
                        "error": str(error),
                    }
                )

                print()
                print("Resultado: FAILED ❌")
                print(f"tipo={type(error).__name__}")
                print(f"error={error}")

        if successful:
            await validate_retrieval_authorization(
                successful,
                settings,
            )

    print()
    print("========================================")
    print(" RESUMEN DE INGESTA")
    print("========================================")

    for result in successful:
        print(
            f"{result['corpus_id']} | "
            f"{result['status']} | "
            f"document_id={result['document_id']} | "
            f"version_id={result['version_id']}"
        )

    for failure in failures:
        print(f"{failure['corpus_id']} | FAILED | {failure['error_type']} | {failure['error']}")

    print()
    print(f"seleccionados={len(selected)}")
    print(f"correctos={len(successful)}")
    print(f"fallidos={len(failures)}")

    if failures:
        print()
        print("FASE 5.12.2: INGESTA INCOMPLETA")

        return 1

    print()
    print("FASE 5.12.2: INGESTA COMPLETADA")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
