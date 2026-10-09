from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from catalina_ingestion.domain.monitoring import (
    IndexingRun,
    IngestionJob,
)


class MonitoringRepository:
    async def list_ingestion_jobs(
        self,
        connection: AsyncConnection[Any],
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IngestionJob]:
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        cursor = await connection.execute(
            """
            SELECT
                j.id,
                j.version_documento_id,
                v.documento_id,
                d.codigo,
                v.version,
                j.tipo,
                j.estado,
                j.progreso,
                j.intento,
                j.max_intentos,
                j.prioridad,
                j.configuracion,
                j.worker_id,
                j.bloqueado_hasta,
                j.fecha_creacion,
                j.fecha_inicio,
                j.fecha_finalizacion,
                j.fecha_actualizacion,
                j.error_codigo,
                j.error_detalle
            FROM catalina.trabajos_ingesta j
            JOIN catalina.versiones_documentos v
              ON v.id = j.version_documento_id
            JOIN catalina.documentos d
              ON d.id = v.documento_id
            ORDER BY j.fecha_creacion DESC, j.id
            LIMIT %s
            OFFSET %s
            """,
            (
                limit,
                offset,
            ),
        )

        rows = await cursor.fetchall()

        return [self._to_ingestion_job(row) for row in rows]

    async def get_ingestion_job(
        self,
        connection: AsyncConnection[Any],
        job_id: UUID,
    ) -> IngestionJob | None:
        cursor = await connection.execute(
            """
            SELECT
                j.id,
                j.version_documento_id,
                v.documento_id,
                d.codigo,
                v.version,
                j.tipo,
                j.estado,
                j.progreso,
                j.intento,
                j.max_intentos,
                j.prioridad,
                j.configuracion,
                j.worker_id,
                j.bloqueado_hasta,
                j.fecha_creacion,
                j.fecha_inicio,
                j.fecha_finalizacion,
                j.fecha_actualizacion,
                j.error_codigo,
                j.error_detalle
            FROM catalina.trabajos_ingesta j
            JOIN catalina.versiones_documentos v
              ON v.id = j.version_documento_id
            JOIN catalina.documentos d
              ON d.id = v.documento_id
            WHERE j.id = %s
            LIMIT 1
            """,
            (job_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_ingestion_job(row)

    async def list_document_jobs(
        self,
        connection: AsyncConnection[Any],
        *,
        document_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IngestionJob]:
        if type(document_id) is not int or document_id < 1:
            raise ValueError("document_id debe ser un entero positivo.")

        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        cursor = await connection.execute(
            """
            SELECT
                j.id,
                j.version_documento_id,
                v.documento_id,
                d.codigo,
                v.version,
                j.tipo,
                j.estado,
                j.progreso,
                j.intento,
                j.max_intentos,
                j.prioridad,
                j.configuracion,
                j.worker_id,
                j.bloqueado_hasta,
                j.fecha_creacion,
                j.fecha_inicio,
                j.fecha_finalizacion,
                j.fecha_actualizacion,
                j.error_codigo,
                j.error_detalle
            FROM catalina.trabajos_ingesta j
            JOIN catalina.versiones_documentos v
              ON v.id = j.version_documento_id
            JOIN catalina.documentos d
              ON d.id = v.documento_id
            WHERE v.documento_id = %s
            ORDER BY j.fecha_creacion DESC, j.id
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

        return [self._to_ingestion_job(row) for row in rows]

    async def document_exists(
        self,
        connection: AsyncConnection[Any],
        document_id: int,
    ) -> bool:
        if type(document_id) is not int or document_id < 1:
            raise ValueError("document_id debe ser un entero positivo.")

        cursor = await connection.execute(
            """
            SELECT 1
            FROM catalina.documentos
            WHERE id = %s
            LIMIT 1
            """,
            (document_id,),
        )

        return await cursor.fetchone() is not None

    async def list_indexing_runs(
        self,
        connection: AsyncConnection[Any],
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IndexingRun]:
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        cursor = await connection.execute(
            """
            SELECT
                e.id,
                e.version_documento_id,
                v.documento_id,
                e.trabajo_ingesta_id,
                d.codigo,
                v.version,
                e.estado,
                e.coleccion_qdrant,
                e.modelo_embedding,
                e.dimension_embedding,
                e.configuracion_fragmentacion,
                e.chunks_esperados,
                e.chunks_indexados,
                e.intento,
                e.fecha_creacion,
                e.fecha_activacion,
                e.fecha_finalizacion,
                e.fecha_actualizacion,
                e.error_codigo,
                e.error_detalle
            FROM catalina.ejecuciones_indexacion e
            JOIN catalina.versiones_documentos v
              ON v.id = e.version_documento_id
            JOIN catalina.documentos d
              ON d.id = v.documento_id
            ORDER BY e.fecha_creacion DESC, e.id
            LIMIT %s
            OFFSET %s
            """,
            (
                limit,
                offset,
            ),
        )

        rows = await cursor.fetchall()

        return [self._to_indexing_run(row) for row in rows]

    async def get_indexing_run(
        self,
        connection: AsyncConnection[Any],
        run_id: UUID,
    ) -> IndexingRun | None:
        cursor = await connection.execute(
            """
            SELECT
                e.id,
                e.version_documento_id,
                v.documento_id,
                e.trabajo_ingesta_id,
                d.codigo,
                v.version,
                e.estado,
                e.coleccion_qdrant,
                e.modelo_embedding,
                e.dimension_embedding,
                e.configuracion_fragmentacion,
                e.chunks_esperados,
                e.chunks_indexados,
                e.intento,
                e.fecha_creacion,
                e.fecha_activacion,
                e.fecha_finalizacion,
                e.fecha_actualizacion,
                e.error_codigo,
                e.error_detalle
            FROM catalina.ejecuciones_indexacion e
            JOIN catalina.versiones_documentos v
              ON v.id = e.version_documento_id
            JOIN catalina.documentos d
              ON d.id = v.documento_id
            WHERE e.id = %s
            LIMIT 1
            """,
            (run_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_indexing_run(row)

    @staticmethod
    def _validate_pagination(
        *,
        limit: int,
        offset: int,
    ) -> None:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit debe estar entre 1 y 100.")

        if type(offset) is not int or offset < 0:
            raise ValueError("offset debe ser mayor o igual a cero.")

    @staticmethod
    def _to_ingestion_job(
        row: tuple[Any, ...],
    ) -> IngestionJob:
        return IngestionJob(
            id=row[0],
            document_version_id=row[1],
            document_id=row[2],
            document_code=row[3],
            version=row[4],
            type=row[5],
            state=row[6],
            progress=row[7],
            attempt=row[8],
            max_attempts=row[9],
            priority=row[10],
            configuration=row[11] or {},
            worker_id=row[12],
            locked_until=row[13],
            created_at=row[14],
            started_at=row[15],
            finished_at=row[16],
            updated_at=row[17],
            error_code=row[18],
            error_detail=row[19],
        )

    @staticmethod
    def _to_indexing_run(
        row: tuple[Any, ...],
    ) -> IndexingRun:
        return IndexingRun(
            id=row[0],
            document_version_id=row[1],
            document_id=row[2],
            ingestion_job_id=row[3],
            document_code=row[4],
            version=row[5],
            state=row[6],
            qdrant_collection=row[7],
            embedding_model=row[8],
            embedding_dimension=row[9],
            chunking_configuration=row[10] or {},
            expected_chunks=row[11],
            indexed_chunks=row[12],
            attempt=row[13],
            created_at=row[14],
            activated_at=row[15],
            finished_at=row[16],
            updated_at=row[17],
            error_code=row[18],
            error_detail=row[19],
        )
