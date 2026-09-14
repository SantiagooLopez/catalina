import unicodedata

from catalina_ingestion.domain.exceptions import EmbeddingError
from catalina_ingestion.domain.query_embedding import QueryEmbedding
from catalina_ingestion.services.embeddings import EmbeddingService


class QueryEmbeddingService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        *,
        max_query_characters: int = 1000,
    ) -> None:
        if max_query_characters < 1:
            raise ValueError("max_query_characters debe ser mayor o igual a 1.")

        self.embedding_service = embedding_service or EmbeddingService()
        self.max_query_characters = max_query_characters

    def normalize(self, query: str) -> str:
        if not isinstance(query, str):
            raise EmbeddingError(
                "INVALID_QUERY_TYPE",
                "La consulta debe ser una cadena de texto.",
            )

        if len(query) > self.max_query_characters:
            raise EmbeddingError(
                "QUERY_TOO_LONG",
                "La consulta supera la longitud permitida.",
                {"max_characters": self.max_query_characters},
            )

        normalized = unicodedata.normalize("NFC", query)

        for character in normalized:
            if unicodedata.category(character).startswith("C") and not character.isspace():
                raise EmbeddingError(
                    "INVALID_QUERY_CHARACTER",
                    "La consulta contiene caracteres de control no permitidos.",
                )

        normalized = " ".join(normalized.split())

        if not normalized:
            raise EmbeddingError(
                "EMPTY_QUERY",
                "La consulta no puede estar vacía.",
            )

        return normalized

    async def generate(self, query: str) -> QueryEmbedding:
        normalized_query = self.normalize(query)

        if self.embedding_service.settings.ollama_truncate:
            raise EmbeddingError(
                "QUERY_TRUNCATION_ENABLED",
                "Configura OLLAMA_TRUNCATE=false para procesar consultas completas.",
            )

        batch = await self.embedding_service.generate_texts([normalized_query])

        if len(batch.vectors) != 1:
            raise EmbeddingError(
                "QUERY_EMBEDDING_COUNT_MISMATCH",
                "Se esperaba exactamente un vector para la consulta.",
            )

        return QueryEmbedding(
            original_query=query,
            normalized_query=normalized_query,
            model=batch.model,
            dimension=batch.dimension,
            vector=batch.vectors[0],
            statistics=batch.statistics,
        )
