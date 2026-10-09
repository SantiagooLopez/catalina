from typing import Any

from psycopg import AsyncConnection

from catalina_ingestion.domain.metrics import (
    IngestionMetrics,
    RagMetrics,
    SystemSummaryMetrics,
)


class MetricsRepository:
    async def get_summary(
        self,
        connection: AsyncConnection[Any],
    ) -> SystemSummaryMetrics:
        cursor = await connection.execute(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM catalina.usuarios
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.usuarios
                    WHERE activo = TRUE
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.conversaciones
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.mensajes
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.documentos
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.documentos
                    WHERE estado = 'activo'
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.documentos
                    WHERE estado = 'inactivo'
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.versiones_documentos
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.versiones_documentos
                    WHERE estado = 'activa'
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.versiones_documentos
                    WHERE estado = 'pendiente'
                ),
                (
                    SELECT COUNT(*)
                    FROM catalina.versiones_documentos
                    WHERE estado = 'fallida'
                )
            """
        )

        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("No fue posible obtener las métricas generales.")

        return SystemSummaryMetrics(
            users_total=row[0],
            users_active=row[1],
            conversations_total=row[2],
            messages_total=row[3],
            documents_total=row[4],
            documents_active=row[5],
            documents_inactive=row[6],
            versions_total=row[7],
            versions_active=row[8],
            versions_pending=row[9],
            versions_failed=row[10],
        )

    async def get_ingestion_metrics(
        self,
        connection: AsyncConnection[Any],
    ) -> IngestionMetrics:
        cursor = await connection.execute(
            """
            SELECT
                COUNT(*),
                COUNT(*) FILTER (
                    WHERE estado = 'pendiente'
                ),
                COUNT(*) FILTER (
                    WHERE estado = 'indexando'
                ),
                COUNT(*) FILTER (
                    WHERE estado = 'completado'
                ),
                COUNT(*) FILTER (
                    WHERE estado = 'fallido'
                ),
                AVG(progreso)
            FROM catalina.trabajos_ingesta
            """
        )

        jobs = await cursor.fetchone()

        if jobs is None:
            raise RuntimeError("No fue posible obtener métricas de ingesta.")

        cursor = await connection.execute(
            """
            SELECT
                COUNT(*),
                COUNT(*) FILTER (
                    WHERE estado = 'preparando'
                ),
                COUNT(*) FILTER (
                    WHERE estado = 'indexando'
                ),
                COUNT(*) FILTER (
                    WHERE estado = 'verificando'
                ),
                COUNT(*) FILTER (
                    WHERE estado = 'activa'
                ),
                COUNT(*) FILTER (
                    WHERE estado = 'fallida'
                )
            FROM catalina.ejecuciones_indexacion
            """
        )

        runs = await cursor.fetchone()

        if runs is None:
            raise RuntimeError("No fue posible obtener métricas de indexación.")

        return IngestionMetrics(
            jobs_total=jobs[0],
            jobs_pending=jobs[1],
            jobs_indexing=jobs[2],
            jobs_completed=jobs[3],
            jobs_failed=jobs[4],
            average_progress=jobs[5],
            indexing_runs_total=runs[0],
            indexing_runs_preparing=runs[1],
            indexing_runs_indexing=runs[2],
            indexing_runs_verifying=runs[3],
            indexing_runs_active=runs[4],
            indexing_runs_failed=runs[5],
        )

    async def get_rag_metrics(
        self,
        connection: AsyncConnection[Any],
    ) -> RagMetrics:
        cursor = await connection.execute(
            """
            SELECT
                COUNT(*),
                COUNT(*) FILTER (
                    WHERE modelo IS NOT NULL
                      AND BTRIM(modelo) <> ''
                ),
                COUNT(*) FILTER (
                    WHERE modelo IS NULL
                       OR BTRIM(modelo) = ''
                ),
                AVG(tiempo_respuesta)
            FROM catalina.mensajes
            """
        )

        messages = await cursor.fetchone()

        if messages is None:
            raise RuntimeError("No fue posible obtener métricas de mensajes.")

        cursor = await connection.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(tokens_input), 0),
                COALESCE(SUM(tokens_output), 0),
                AVG(satisfaccion),
                AVG(precision)
            FROM catalina.metricas
            """
        )

        metrics = await cursor.fetchone()

        if metrics is None:
            raise RuntimeError("No fue posible obtener métricas RAG.")

        return RagMetrics(
            messages_total=messages[0],
            messages_with_model=messages[1],
            messages_without_model=messages[2],
            average_response_time_seconds=messages[3],
            metric_records=metrics[0],
            tokens_input_total=metrics[1],
            tokens_output_total=metrics[2],
            average_satisfaction=metrics[3],
            average_precision=metrics[4],
        )
