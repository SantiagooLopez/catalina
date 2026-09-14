from collections.abc import Sequence
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from catalina_ingestion.core.config import Settings
from catalina_ingestion.domain.embeddings import EmbeddedDocument
from catalina_ingestion.domain.indexing import (
    ChunkManifest,
    IndexingContext,
)
from catalina_ingestion.domain.processed import ProcessedDocument


class IndexingRepository:
    async def create_execution(
        self,
        connection: AsyncConnection[Any],
        context: IndexingContext,
        embedded: EmbeddedDocument,
        settings: Settings,
    ) -> UUID:
        cursor = await connection.execute(
            """
            INSERT INTO catalina.ejecuciones_indexacion (
                version_documento_id,
                trabajo_ingesta_id,
                estado,
                coleccion_qdrant,
                modelo_embedding,
                dimension_embedding,
                configuracion_fragmentacion,
                chunks_esperados,
                chunks_indexados
            )
            VALUES (
                %s, %s, 'preparando', %s, %s, %s, %s, %s, 0
            )
            RETURNING id
            """,
            (
                context.document_version_id,
                context.ingestion_job_id,
                settings.qdrant_collection,
                embedded.model,
                embedded.dimension,
                Jsonb(
                    {
                        "target_size": settings.chunk_target_size,
                        "overlap": settings.chunk_overlap,
                        "minimum_size": settings.chunk_min_size,
                    }
                ),
                len(embedded.chunks),
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("No fue posible crear la ejecución de indexación.")

        return row[0]

    async def mark_indexing(
        self,
        connection: AsyncConnection[Any],
        run_id: UUID,
        job_id: UUID,
    ) -> None:
        await connection.execute(
            """
            UPDATE catalina.ejecuciones_indexacion
            SET estado = 'indexando'
            WHERE id = %s
            """,
            (run_id,),
        )

        await connection.execute(
            """
            UPDATE catalina.trabajos_ingesta
            SET estado = 'indexando',
                progreso = 80,
                fecha_inicio = COALESCE(
                    fecha_inicio,
                    CURRENT_TIMESTAMP
                )
            WHERE id = %s
            """,
            (job_id,),
        )

    async def mark_verifying(
        self,
        connection: AsyncConnection[Any],
        run_id: UUID,
        indexed_count: int,
    ) -> None:
        await connection.execute(
            """
            UPDATE catalina.ejecuciones_indexacion
            SET estado = 'verificando',
                chunks_indexados = %s
            WHERE id = %s
            """,
            (indexed_count, run_id),
        )

    async def activate(
        self,
        connection: AsyncConnection[Any],
        context: IndexingContext,
        run_id: UUID,
        manifests: Sequence[ChunkManifest],
        processed: ProcessedDocument,
        embedded: EmbeddedDocument,
    ) -> None:
        await connection.execute(
            """
            SELECT id
            FROM catalina.versiones_documentos
            WHERE id = %s
            FOR UPDATE
            """,
            (context.document_version_id,),
        )

        await connection.execute(
            """
            UPDATE catalina.versiones_documentos
            SET estado = 'reemplazada'
            WHERE documento_id = %s
              AND id <> %s
              AND estado = 'activa'
            """,
            (
                context.document_id,
                context.document_version_id,
            ),
        )

        await connection.execute(
            """
            UPDATE catalina.ejecuciones_indexacion
            SET estado = 'reemplazada',
                fecha_finalizacion = CURRENT_TIMESTAMP
            WHERE version_documento_id = %s
              AND id <> %s
              AND estado = 'activa'
            """,
            (context.document_version_id, run_id),
        )

        records = [
            (
                manifest.point_id,
                run_id,
                context.document_version_id,
                manifest.chunk_index,
                manifest.page_start,
                manifest.page_end,
                manifest.section,
                manifest.character_count,
                manifest.estimated_tokens,
                manifest.text_sha256,
                Jsonb(manifest.metadata),
            )
            for manifest in manifests
        ]

        async with connection.cursor() as cursor:
            await cursor.executemany(
                """
                INSERT INTO catalina.fragmentos_documento (
                    id,
                    ejecucion_indexacion_id,
                    version_documento_id,
                    chunk_index,
                    pagina_inicio,
                    pagina_fin,
                    seccion,
                    cantidad_caracteres,
                    cantidad_tokens,
                    hash_texto,
                    metadatos
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO NOTHING
                """,
                records,
            )

        await connection.execute(
            """
            UPDATE catalina.ejecuciones_indexacion
            SET estado = 'activa',
                chunks_indexados = %s,
                fecha_activacion = CURRENT_TIMESTAMP,
                fecha_finalizacion = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (len(manifests), run_id),
        )

        await connection.execute(
            """
            UPDATE catalina.versiones_documentos
            SET estado = 'activa',
                ejecucion_indexacion_activa_id = %s,
                hash_contenido = %s,
                total_paginas = %s,
                total_secciones = %s,
                total_chunks = %s,
                modelo_embedding = %s,
                dimension_embedding = %s,
                fecha_indexacion = CURRENT_TIMESTAMP,
                error_codigo = NULL,
                error_detalle = NULL
            WHERE id = %s
            """,
            (
                run_id,
                processed.content_sha256,
                processed.page_count,
                processed.section_count,
                len(processed.chunks),
                embedded.model,
                embedded.dimension,
                context.document_version_id,
            ),
        )

        await connection.execute(
            """
            UPDATE catalina.trabajos_ingesta
            SET estado = 'completado',
                progreso = 100,
                fecha_finalizacion = CURRENT_TIMESTAMP,
                error_codigo = NULL,
                error_detalle = NULL
            WHERE id = %s
            """,
            (context.ingestion_job_id,),
        )

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
                'indexing_completed',
                'Documento indexado y ejecución activada.',
                'ejecucion_indexacion',
                %s,
                'info',
                %s,
                %s
            )
            """,
            (
                str(run_id),
                context.ingestion_job_id,
                Jsonb(
                    {
                        "document_id": context.document_id,
                        "version_id": (context.document_version_id),
                        "chunks": len(manifests),
                        "content_sha256": (processed.content_sha256),
                    }
                ),
            ),
        )

    async def mark_failed(
        self,
        connection: AsyncConnection[Any],
        context: IndexingContext,
        run_id: UUID,
        error_code: str,
        error_detail: str,
    ) -> None:
        await connection.execute(
            """
            UPDATE catalina.ejecuciones_indexacion
            SET estado = 'fallida',
                fecha_finalizacion = CURRENT_TIMESTAMP,
                error_codigo = %s,
                error_detalle = %s
            WHERE id = %s
            """,
            (error_code, error_detail, run_id),
        )

        await connection.execute(
            """
            UPDATE catalina.trabajos_ingesta
            SET estado = 'fallido',
                error_codigo = %s,
                error_detalle = %s,
                fecha_finalizacion = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                error_code,
                error_detail,
                context.ingestion_job_id,
            ),
        )

        await connection.execute(
            """
            UPDATE catalina.versiones_documentos
            SET estado = CASE
                    WHEN ejecucion_indexacion_activa_id IS NULL
                    THEN 'fallida'
                    ELSE estado
                END,
                error_codigo = %s,
                error_detalle = %s
            WHERE id = %s
            """,
            (
                error_code,
                error_detail,
                context.document_version_id,
            ),
        )
