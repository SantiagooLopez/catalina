from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from qdrant_client import AsyncQdrantClient, models

from catalina_ingestion.clients.qdrant import (
    get_qdrant_client,
)
from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.db.postgres import get_postgres_pool
from catalina_ingestion.domain.embeddings import EmbeddedDocument
from catalina_ingestion.domain.exceptions import (
    IndexingError,
    IngestionError,
)
from catalina_ingestion.domain.indexing import (
    ChunkManifest,
    IndexingContext,
    IndexingResult,
)
from catalina_ingestion.domain.processed import ProcessedDocument
from catalina_ingestion.repositories.indexing import (
    IndexingRepository,
)


class QdrantIndexingService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncQdrantClient | None = None,
        repository: IndexingRepository | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client
        self.repository = repository or IndexingRepository()

    async def index(
        self,
        context: IndexingContext,
        processed: ProcessedDocument,
        embedded: EmbeddedDocument,
    ) -> IndexingResult:
        self._validate_inputs(processed, embedded)

        client = self.client or get_qdrant_client()
        pool = get_postgres_pool()
        run_id: UUID | None = None
        activated = False

        try:
            async with pool.connection() as connection:
                async with connection.transaction():
                    run_id = await self.repository.create_execution(
                        connection,
                        context,
                        embedded,
                        self.settings,
                    )

                    await self.repository.mark_indexing(
                        connection,
                        run_id,
                        context.ingestion_job_id,
                    )

            points, manifests = self._build_points(
                context,
                processed,
                embedded,
                run_id,
            )

            batch_size = self.settings.qdrant_upsert_batch_size

            for start in range(0, len(points), batch_size):
                await client.upsert(
                    collection_name=(self.settings.qdrant_collection),
                    points=points[start : start + batch_size],
                    wait=True,
                )

            run_filter = self._run_filter(run_id)

            count_result = await client.count(
                collection_name=(self.settings.qdrant_collection),
                count_filter=run_filter,
                exact=True,
            )

            if count_result.count != len(points):
                raise IndexingError(
                    "QDRANT_POINT_COUNT_MISMATCH",
                    "Qdrant no almacenó todos los chunks.",
                    {
                        "expected": len(points),
                        "received": count_result.count,
                        "index_run_id": str(run_id),
                    },
                )

            async with pool.connection() as connection:
                async with connection.transaction():
                    await self.repository.mark_verifying(
                        connection,
                        run_id,
                        count_result.count,
                    )

                    await self.repository.activate(
                        connection,
                        context,
                        run_id,
                        manifests,
                        processed,
                        embedded,
                    )

            activated = True

            return IndexingResult(
                index_run_id=run_id,
                point_count=count_result.count,
                point_ids=tuple(manifest.point_id for manifest in manifests),
                collection=self.settings.qdrant_collection,
                state="activa",
            )

        except Exception as error:
            if run_id is not None and not activated:
                try:
                    await client.delete(
                        collection_name=(self.settings.qdrant_collection),
                        points_selector=models.FilterSelector(filter=self._run_filter(run_id)),
                        wait=True,
                    )
                except Exception:
                    pass

                error_code = (
                    error.code if isinstance(error, IngestionError) else "QDRANT_INDEXING_FAILED"
                )

                try:
                    async with pool.connection() as connection:
                        async with connection.transaction():
                            await self.repository.mark_failed(
                                connection,
                                context,
                                run_id,
                                error_code,
                                str(error)[:4000],
                            )
                except Exception:
                    pass

            if isinstance(error, IndexingError):
                raise

            raise IndexingError(
                "QDRANT_INDEXING_FAILED",
                "No fue posible completar la indexación.",
                {"error_type": type(error).__name__},
            ) from error

    def _validate_inputs(
        self,
        processed: ProcessedDocument,
        embedded: EmbeddedDocument,
    ) -> None:
        if not processed.chunks:
            raise IndexingError(
                "NO_CHUNKS_TO_INDEX",
                "No existen chunks para indexar.",
            )

        if len(processed.chunks) != len(embedded.chunks):
            raise IndexingError(
                "CHUNK_EMBEDDING_COUNT_MISMATCH",
                "La cantidad de chunks y embeddings no coincide.",
            )

        if embedded.dimension != self.settings.embedding_dimension:
            raise IndexingError(
                "INDEX_DIMENSION_MISMATCH",
                "La dimensión del embedding no coincide.",
            )

        for chunk, embedded_chunk in zip(
            processed.chunks,
            embedded.chunks,
            strict=True,
        ):
            if (
                chunk.index != embedded_chunk.chunk.index
                or chunk.text_sha256 != embedded_chunk.chunk.text_sha256
            ):
                raise IndexingError(
                    "CHUNK_ORDER_MISMATCH",
                    "El orden de chunks y embeddings cambió.",
                )

    def _build_points(
        self,
        context: IndexingContext,
        processed: ProcessedDocument,
        embedded: EmbeddedDocument,
        run_id: UUID,
    ) -> tuple[
        list[models.PointStruct],
        list[ChunkManifest],
    ]:
        points: list[models.PointStruct] = []
        manifests: list[ChunkManifest] = []
        indexed_at = datetime.now(UTC).isoformat()

        for embedded_chunk in embedded.chunks:
            chunk = embedded_chunk.chunk

            point_id = uuid5(
                NAMESPACE_URL,
                (f"catalina/{run_id}/{chunk.index}/{chunk.text_sha256}"),
            )

            payload = {
                "schema_version": 1,
                "document_id": context.document_id,
                "document_version_id": (context.document_version_id),
                "index_run_id": str(run_id),
                "chunk_index": chunk.index,
                "document_name": context.document_name,
                "version": context.version,
                "category": context.category,
                "language": context.language,
                "source_file": context.source_file,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "section": chunk.section,
                "text": chunk.text,
                "text_sha256": chunk.text_sha256,
                "content_sha256": processed.content_sha256,
                "embedding_model": embedded.model,
                "indexed_at": indexed_at,
                "metadata": context.metadata,
            }

            points.append(
                models.PointStruct(
                    id=str(point_id),
                    vector=list(embedded_chunk.vector),
                    payload=payload,
                )
            )

            manifests.append(
                ChunkManifest(
                    point_id=point_id,
                    chunk_index=chunk.index,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section=chunk.section,
                    character_count=chunk.character_count,
                    estimated_tokens=chunk.estimated_tokens,
                    text_sha256=chunk.text_sha256,
                    metadata={
                        "collection": (self.settings.qdrant_collection),
                        "index_run_id": str(run_id),
                    },
                )
            )

        return points, manifests

    def _run_filter(self, run_id: UUID) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="index_run_id",
                    match=models.MatchValue(value=str(run_id)),
                )
            ]
        )
