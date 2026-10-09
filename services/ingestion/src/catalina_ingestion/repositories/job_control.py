from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb


@dataclass(frozen=True, slots=True)
class RetryableJob:
    id: UUID
    document_version_id: int
    document_id: int
    type: str
    state: str
    attempt: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class ReindexableVersion:
    id: int
    document_id: int
    document_state: str
    version: str
    state: str
    file_hash: str | None


class JobControlRepository:
    async def get_job_for_update(
        self,
        connection: AsyncConnection[Any],
        job_id: UUID,
    ) -> RetryableJob | None:
        cursor = await connection.execute(
            """
            SELECT
                j.id,
                j.version_documento_id,
                v.documento_id,
                j.tipo,
                j.estado,
                j.intento,
                j.max_intentos
            FROM catalina.trabajos_ingesta j
            JOIN catalina.versiones_documentos v
              ON v.id = j.version_documento_id
            WHERE j.id = %s
            FOR UPDATE OF j
            """,
            (job_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return RetryableJob(
            id=row[0],
            document_version_id=row[1],
            document_id=row[2],
            type=row[3],
            state=row[4],
            attempt=row[5],
            max_attempts=row[6],
        )

    async def reset_failed_job(
        self,
        connection: AsyncConnection[Any],
        job_id: UUID,
    ) -> None:
        await connection.execute(
            """
            UPDATE catalina.trabajos_ingesta
            SET
                estado = 'pendiente',
                progreso = 0,
                worker_id = NULL,
                bloqueado_hasta = NULL,
                fecha_inicio = NULL,
                fecha_finalizacion = NULL,
                fecha_actualizacion = CURRENT_TIMESTAMP,
                error_codigo = NULL,
                error_detalle = NULL
            WHERE id = %s
            """,
            (job_id,),
        )

    async def get_version_for_update(
        self,
        connection: AsyncConnection[Any],
        *,
        document_id: int,
        version_id: int,
    ) -> ReindexableVersion | None:
        cursor = await connection.execute(
            """
            SELECT
                v.id,
                v.documento_id,
                d.estado,
                v.version,
                v.estado,
                v.hash_archivo
            FROM catalina.versiones_documentos v
            JOIN catalina.documentos d
              ON d.id = v.documento_id
            WHERE v.id = %s
              AND v.documento_id = %s
            FOR UPDATE OF v
            """,
            (
                version_id,
                document_id,
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return ReindexableVersion(
            id=row[0],
            document_id=row[1],
            document_state=row[2],
            version=row[3],
            state=row[4],
            file_hash=row[5],
        )

    async def find_open_reindex_job(
        self,
        connection: AsyncConnection[Any],
        *,
        version_id: int,
    ) -> UUID | None:
        cursor = await connection.execute(
            """
            SELECT id
            FROM catalina.trabajos_ingesta
            WHERE version_documento_id = %s
              AND tipo = 'reindexacion'
              AND estado NOT IN (
                  'completado',
                  'fallido'
              )
            ORDER BY fecha_creacion DESC
            LIMIT 1
            """,
            (version_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return row[0]

    async def write_retry_audit(
        self,
        connection: AsyncConnection[Any],
        *,
        job: RetryableJob,
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
            VALUES (
                'ingestion_job_retried',
                'Trabajo de ingesta reenviado a la cola.',
                'trabajo_ingesta',
                %s,
                'info',
                %s,
                %s
            )
            """,
            (
                str(job.id),
                job.id,
                Jsonb(
                    {
                        "document_id": (job.document_id),
                        "version_id": (job.document_version_id),
                        "attempt": job.attempt,
                        "max_attempts": (job.max_attempts),
                    }
                ),
            ),
        )

    async def write_reindex_audit(
        self,
        connection: AsyncConnection[Any],
        *,
        job_id: UUID,
        version: ReindexableVersion,
        reason: str,
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
            VALUES (
                'document_reindex_requested',
                'Reindexación solicitada administrativamente.',
                'version_documento',
                %s,
                'info',
                %s,
                %s
            )
            """,
            (
                str(version.id),
                job_id,
                Jsonb(
                    {
                        "document_id": (version.document_id),
                        "version_id": version.id,
                        "version": version.version,
                        "reason": reason,
                    }
                ),
            ),
        )
