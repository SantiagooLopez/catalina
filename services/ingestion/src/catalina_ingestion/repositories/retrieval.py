from catalina_ingestion.core.config import Settings
from catalina_ingestion.db.postgres import get_postgres_pool


class RetrievalRepository:
    async def active_runs(
        self,
        settings: Settings,
    ) -> dict[str, tuple[int, int]]:
        pool = get_postgres_pool()

        async with pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT
                    e.id,
                    d.id,
                    v.id
                FROM catalina.documentos AS d
                JOIN catalina.versiones_documentos AS v
                    ON v.documento_id = d.id
                JOIN catalina.ejecuciones_indexacion AS e
                    ON e.id = v.ejecucion_indexacion_activa_id
                   AND e.version_documento_id = v.id
                WHERE d.estado = 'activo'
                  AND v.estado = 'activa'
                  AND e.estado = 'activa'
                  AND e.coleccion_qdrant = %s
                  AND e.modelo_embedding = %s
                  AND e.dimension_embedding = %s
                  AND e.chunks_esperados > 0
                  AND e.chunks_indexados = e.chunks_esperados
                """,
                (
                    settings.qdrant_collection,
                    settings.ollama_embedding_model,
                    settings.embedding_dimension,
                ),
            )
            rows = await cursor.fetchall()

        return {str(run_id): (document_id, version_id) for run_id, document_id, version_id in rows}
