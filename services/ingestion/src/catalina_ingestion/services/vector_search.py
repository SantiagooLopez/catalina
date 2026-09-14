import math

from pydantic import ValidationError
from qdrant_client import AsyncQdrantClient, models

from catalina_ingestion.clients.qdrant import get_qdrant_client
from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.domain.retrieval import (
    RetrievalQuery,
    RetrievedChunk,
)
from catalina_ingestion.domain.search import (
    CandidateSearchResult,
    IndexedPayload,
    SearchError,
)
from catalina_ingestion.repositories.retrieval import RetrievalRepository
from catalina_ingestion.services.embeddings import EmbeddingService
from catalina_ingestion.services.query_embedding import QueryEmbeddingService
from catalina_ingestion.services.retrieval_filters import (
    build_retrieval_filter,
)


class VectorSearchService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncQdrantClient | None = None,
        repository: RetrievalRepository | None = None,
        query_service: QueryEmbeddingService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client
        self.repository = repository or RetrievalRepository()
        self.query_service = query_service or QueryEmbeddingService(
            embedding_service=EmbeddingService(settings=self.settings)
        )

    async def search(
        self,
        query: RetrievalQuery,
    ) -> CandidateSearchResult:
        if not 1 <= query.top_k <= query.candidate_k <= 100:
            raise ValueError("Se requiere 1 <= top_k <= candidate_k <= 100.")

        if not math.isfinite(query.score_threshold):
            raise ValueError("El umbral debe ser finito.")

        normalized = self.query_service.normalize(query.query)
        runs = await self.repository.active_runs(self.settings)

        if not runs:
            return CandidateSearchResult(
                query=normalized,
                chunks=(),
                returned_by_qdrant=0,
                discarded_after_recheck=0,
            )

        client = self.client or get_qdrant_client()
        info = await client.get_collection(self.settings.qdrant_collection)
        vector_config = info.config.params.vectors

        if (
            not isinstance(vector_config, models.VectorParams)
            or vector_config.size != self.settings.embedding_dimension
            or vector_config.distance != models.Distance.COSINE
        ):
            raise SearchError(
                "La colección debe usar un vector sin nombre, "
                "la dimensión configurada y distancia Cosine."
            )

        embedding = await self.query_service.generate(query.query)

        if (
            embedding.model != self.settings.ollama_embedding_model
            or embedding.dimension != self.settings.embedding_dimension
            or len(embedding.vector) != self.settings.embedding_dimension
            or not all(math.isfinite(x) for x in embedding.vector)
            or not any(x != 0 for x in embedding.vector)
        ):
            raise SearchError("El embedding de consulta no es compatible.")

        search_filter = build_retrieval_filter(
            run_ids=list(runs),
            model=embedding.model,
            filters=query.filters,
        )

        response = await client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=list(embedding.vector),
            query_filter=search_filter,
            limit=query.candidate_k,
            score_threshold=query.score_threshold,
            with_payload=True,
            with_vectors=False,
        )

        # Comprueba si cambió la vigencia durante la búsqueda.
        current_runs = await self.repository.active_runs(self.settings)
        chunks: list[RetrievedChunk] = []
        discarded = 0

        for point in response.points:
            try:
                payload = IndexedPayload.model_validate(point.payload or {})
            except ValidationError as error:
                raise SearchError(f"Payload inválido en el punto {point.id}.") from error

            identity = (
                payload.document_id,
                payload.document_version_id,
            )

            if runs.get(payload.index_run_id) != identity:
                raise SearchError(
                    f"El punto {point.id} no pertenece al alcance autorizado de búsqueda."
                )

            if current_runs.get(payload.index_run_id) != identity:
                discarded += 1
                continue

            if payload.embedding_model != embedding.model:
                raise SearchError(f"Modelo incompatible en el punto {point.id}.")

            if not math.isfinite(point.score):
                raise SearchError(f"Score no finito en el punto {point.id}.")

            if point.score < query.score_threshold:
                raise SearchError(f"Score inferior al umbral en el punto {point.id}.")

            values = payload.model_dump(exclude={"schema_version", "index_run_id"})

            # Los campos reservados prevalecen sobre metadata del usuario.
            values["metadata"] = {
                **payload.metadata,
                "index_run_id": payload.index_run_id,
                "schema_version": payload.schema_version,
            }

            chunks.append(
                RetrievedChunk(
                    point_id=str(point.id),
                    score=float(point.score),
                    **values,
                )
            )

        chunks.sort(key=lambda chunk: (-chunk.score, chunk.point_id))

        return CandidateSearchResult(
            query=embedding.normalized_query,
            chunks=tuple(chunks),
            returned_by_qdrant=len(response.points),
            discarded_after_recheck=discarded,
        )
