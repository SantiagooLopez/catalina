from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from catalina_ingestion.core.config import Settings
from catalina_ingestion.domain.files import ValidatedFile
from catalina_ingestion.schemas.documents import (
    DocumentRegistrationRequest,
)


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    id: int
    codigo: str
    nombre: str
    categoria: str
    created: bool


@dataclass(frozen=True, slots=True)
class ExistingVersion:
    document_id: int
    version_id: int
    version: str
    estado: str
    ruta_archivo: str | None


class DocumentRepository:
    async def find_version_by_hash(
        self,
        connection: AsyncConnection[Any],
        sha256: str,
    ) -> ExistingVersion | None:
        cursor = await connection.execute(
            """
            SELECT
                documento_id,
                id,
                version,
                estado,
                ruta_archivo
            FROM catalina.versiones_documentos
            WHERE LOWER(hash_archivo) = LOWER(%s)
            LIMIT 1
            """,
            (sha256,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return ExistingVersion(
            document_id=row[0],
            version_id=row[1],
            version=row[2],
            estado=row[3],
            ruta_archivo=row[4],
        )

    async def get_or_create_document(
        self,
        connection: AsyncConnection[Any],
        request: DocumentRegistrationRequest,
        validated_file: ValidatedFile,
    ) -> DocumentRecord:
        cursor = await connection.execute(
            """
            INSERT INTO catalina.documentos (
                nombre,
                tipo_archivo,
                categoria,
                descripcion,
                estado,
                codigo,
                idioma,
                origen,
                metadatos
            )
            VALUES (%s, %s, %s, %s, 'activo', %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id, codigo, nombre, categoria
            """,
            (
                request.nombre,
                validated_file.extension.lstrip(".").upper(),
                request.categoria,
                request.descripcion,
                request.codigo,
                request.idioma,
                request.origen,
                Jsonb(request.metadatos),
            ),
        )

        row = await cursor.fetchone()

        if row is not None:
            return DocumentRecord(
                id=row[0],
                codigo=row[1],
                nombre=row[2],
                categoria=row[3],
                created=True,
            )

        cursor = await connection.execute(
            """
            SELECT id, codigo, nombre, categoria
            FROM catalina.documentos
            WHERE codigo = %s
            FOR UPDATE
            """,
            (request.codigo,),
        )

        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("No fue posible crear ni recuperar el documento.")

        return DocumentRecord(
            id=row[0],
            codigo=row[1],
            nombre=row[2],
            categoria=row[3],
            created=False,
        )

    async def find_version_by_label(
        self,
        connection: AsyncConnection[Any],
        document_id: int,
        version: str,
    ) -> ExistingVersion | None:
        cursor = await connection.execute(
            """
            SELECT
                documento_id,
                id,
                version,
                estado,
                ruta_archivo
            FROM catalina.versiones_documentos
            WHERE documento_id = %s
              AND version = %s
            LIMIT 1
            """,
            (document_id, version),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return ExistingVersion(
            document_id=row[0],
            version_id=row[1],
            version=row[2],
            estado=row[3],
            ruta_archivo=row[4],
        )

    async def create_version(
        self,
        connection: AsyncConnection[Any],
        document_id: int,
        request: DocumentRegistrationRequest,
        validated_file: ValidatedFile,
        settings: Settings,
    ) -> int:
        cursor = await connection.execute(
            """
            INSERT INTO catalina.versiones_documentos (
                documento_id,
                version,
                ruta_archivo,
                hash_archivo,
                nombre_archivo_original,
                extension,
                mime_type,
                tamano_bytes,
                estado,
                total_paginas,
                modelo_embedding,
                dimension_embedding,
                configuracion_fragmentacion
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                'cargada', %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                document_id,
                request.version,
                str(validated_file.staging_path),
                validated_file.sha256,
                validated_file.original_name,
                validated_file.extension,
                validated_file.mime_type,
                validated_file.size_bytes,
                validated_file.page_count,
                settings.ollama_embedding_model,
                settings.embedding_dimension,
                Jsonb(
                    {
                        "target_size": settings.chunk_target_size,
                        "overlap": settings.chunk_overlap,
                        "minimum_size": settings.chunk_min_size,
                    }
                ),
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("No fue posible crear la versión.")

        return row[0]

    async def mark_version_pending(
        self,
        connection: AsyncConnection[Any],
        version_id: int,
        storage_path: Path,
    ) -> None:
        await connection.execute(
            """
            UPDATE catalina.versiones_documentos
            SET ruta_archivo = %s,
                estado = 'pendiente',
                error_codigo = NULL,
                error_detalle = NULL
            WHERE id = %s
            """,
            (str(storage_path), version_id),
        )

    async def create_ingestion_job(
        self,
        connection: AsyncConnection[Any],
        version_id: int,
        sha256: str,
        settings: Settings,
    ) -> UUID:
        configuration = {
            "embedding_model": settings.ollama_embedding_model,
            "embedding_dimension": settings.embedding_dimension,
            "embedding_batch_size": settings.embedding_batch_size,
            "chunk_target_size": settings.chunk_target_size,
            "chunk_overlap": settings.chunk_overlap,
            "chunk_min_size": settings.chunk_min_size,
        }

        cursor = await connection.execute(
            """
            INSERT INTO catalina.trabajos_ingesta (
                version_documento_id,
                tipo,
                estado,
                progreso,
                max_intentos,
                idempotency_key,
                configuracion
            )
            VALUES (%s, 'ingesta', 'pendiente', 0, %s, %s, %s)
            RETURNING id
            """,
            (
                version_id,
                settings.worker_max_attempts,
                f"ingesta:{version_id}:{sha256}",
                Jsonb(configuration),
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("No fue posible crear el trabajo de ingesta.")

        return row[0]

    async def create_reindexing_job(
        self,
        connection: AsyncConnection[Any],
        version_id: int,
        sha256: str,
        settings: Settings,
        reason: str,
    ) -> UUID:
        reason = reason.strip()

        if not reason:
            raise ValueError("reason no puede estar vacío para una reindexación.")

        configuration = {
            "embedding_model": settings.ollama_embedding_model,
            "embedding_dimension": settings.embedding_dimension,
            "embedding_batch_size": settings.embedding_batch_size,
            "chunk_target_size": settings.chunk_target_size,
            "chunk_overlap": settings.chunk_overlap,
            "chunk_min_size": settings.chunk_min_size,
            "reindex_reason": reason,
        }

        cursor = await connection.execute(
            """
            INSERT INTO catalina.trabajos_ingesta (
                version_documento_id,
                tipo,
                estado,
                progreso,
                max_intentos,
                idempotency_key,
                configuracion
            )
            VALUES (
                %s,
                'reindexacion',
                'pendiente',
                0,
                %s,
                %s,
                %s
            )
            RETURNING id
            """,
            (
                version_id,
                settings.worker_max_attempts,
                (f"reindexacion:{version_id}:{sha256}:{reason}"),
                Jsonb(configuration),
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("No fue posible crear el trabajo de reindexación.")

        return row[0]

    async def write_audit(
        self,
        connection: AsyncConnection[Any],
        document_id: int,
        version_id: int,
        job_id: UUID,
        sha256: str,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO catalina.auditoria (
                evento,
                detalle,
                entidad_tipo,
                entidad_id,
                nivel,
                correlation_id,
                datos
            )
            VALUES (%s, %s, %s, %s, 'info', %s, %s)
            """,
            (
                "document_version_registered",
                "Documento validado y trabajo de ingesta creado.",
                "version_documento",
                str(version_id),
                job_id,
                Jsonb(
                    {
                        "document_id": document_id,
                        "version_id": version_id,
                        "sha256": sha256,
                    }
                ),
            ),
        )
