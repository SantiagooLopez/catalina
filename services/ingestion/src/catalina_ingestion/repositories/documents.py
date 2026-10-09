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


@dataclass(frozen=True, slots=True)
class DocumentDetail:
    id: int
    nombre: str
    tipo_archivo: str | None
    categoria: str | None
    descripcion: str | None
    estado: str | None
    fecha_carga: Any
    codigo: str | None
    idioma: str
    origen: str | None
    metadatos: dict[str, Any]
    fecha_actualizacion: Any


@dataclass(frozen=True, slots=True)
class DocumentVersionDetail:
    id: int
    documento_id: int | None
    version: str
    nombre_archivo_original: str | None
    extension: str | None
    mime_type: str | None
    tamano_bytes: int | None
    hash_contenido: str | None
    estado: str
    total_paginas: int | None
    total_secciones: int | None
    total_chunks: int | None
    modelo_embedding: str | None
    dimension_embedding: int | None
    fecha_indexacion: Any
    fecha_actualizacion: Any
    error_codigo: str | None
    error_detalle: str | None


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

    async def list_documents(
        self,
        connection: AsyncConnection[Any],
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DocumentDetail]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit debe estar entre 1 y 100.")

        if type(offset) is not int or offset < 0:
            raise ValueError("offset debe ser mayor o igual a cero.")

        cursor = await connection.execute(
            """
            SELECT
                id,
                nombre,
                tipo_archivo,
                categoria,
                descripcion,
                estado,
                fecha_carga,
                codigo,
                idioma,
                origen,
                metadatos,
                fecha_actualizacion
            FROM catalina.documentos
            ORDER BY fecha_actualizacion DESC, id DESC
            LIMIT %s
            OFFSET %s
            """,
            (
                limit,
                offset,
            ),
        )

        rows = await cursor.fetchall()

        return [self._to_document_detail(row) for row in rows]

    async def get_document(
        self,
        connection: AsyncConnection[Any],
        document_id: int,
    ) -> DocumentDetail | None:
        if type(document_id) is not int or document_id < 1:
            raise ValueError("document_id debe ser un entero positivo.")

        cursor = await connection.execute(
            """
            SELECT
                id,
                nombre,
                tipo_archivo,
                categoria,
                descripcion,
                estado,
                fecha_carga,
                codigo,
                idioma,
                origen,
                metadatos,
                fecha_actualizacion
            FROM catalina.documentos
            WHERE id = %s
            LIMIT 1
            """,
            (document_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_document_detail(row)

    async def list_versions(
        self,
        connection: AsyncConnection[Any],
        *,
        document_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DocumentVersionDetail]:
        if type(document_id) is not int or document_id < 1:
            raise ValueError("document_id debe ser un entero positivo.")

        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit debe estar entre 1 y 100.")

        if type(offset) is not int or offset < 0:
            raise ValueError("offset debe ser mayor o igual a cero.")

        cursor = await connection.execute(
            """
            SELECT
                id,
                documento_id,
                version,
                nombre_archivo_original,
                extension,
                mime_type,
                tamano_bytes,
                hash_contenido,
                estado,
                total_paginas,
                total_secciones,
                total_chunks,
                modelo_embedding,
                dimension_embedding,
                fecha_indexacion,
                fecha_actualizacion,
                error_codigo,
                error_detalle
            FROM catalina.versiones_documentos
            WHERE documento_id = %s
            ORDER BY fecha_creacion DESC, id DESC
            LIMIT %s
            OFFSET %s
            """,
            (
                document_id,
                limit,
                offset,
            ),
        )

        rows = await cursor.fetchall()

        return [self._to_version_detail(row) for row in rows]

    async def set_document_status(
        self,
        connection: AsyncConnection[Any],
        *,
        document_id: int,
        status: str,
    ) -> DocumentDetail | None:
        if type(document_id) is not int or document_id < 1:
            raise ValueError("document_id debe ser un entero positivo.")

        normalized = status.strip().lower()

        if normalized not in {
            "activo",
            "inactivo",
        }:
            raise ValueError("Estado documental no soportado.")

        cursor = await connection.execute(
            """
            UPDATE catalina.documentos
            SET
                estado = %s,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING
                id,
                nombre,
                tipo_archivo,
                categoria,
                descripcion,
                estado,
                fecha_carga,
                codigo,
                idioma,
                origen,
                metadatos,
                fecha_actualizacion
            """,
            (
                normalized,
                document_id,
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_document_detail(row)

    @staticmethod
    def _to_document_detail(
        row: tuple[Any, ...],
    ) -> DocumentDetail:
        return DocumentDetail(
            id=row[0],
            nombre=row[1],
            tipo_archivo=row[2],
            categoria=row[3],
            descripcion=row[4],
            estado=row[5],
            fecha_carga=row[6],
            codigo=row[7],
            idioma=row[8],
            origen=row[9],
            metadatos=row[10] or {},
            fecha_actualizacion=row[11],
        )

    @staticmethod
    def _to_version_detail(
        row: tuple[Any, ...],
    ) -> DocumentVersionDetail:
        return DocumentVersionDetail(
            id=row[0],
            documento_id=row[1],
            version=row[2],
            nombre_archivo_original=row[3],
            extension=row[4],
            mime_type=row[5],
            tamano_bytes=row[6],
            hash_contenido=row[7],
            estado=row[8],
            total_paginas=row[9],
            total_secciones=row[10],
            total_chunks=row[11],
            modelo_embedding=row[12],
            dimension_embedding=row[13],
            fecha_indexacion=row[14],
            fecha_actualizacion=row[15],
            error_codigo=row[16],
            error_detalle=row[17],
        )

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
