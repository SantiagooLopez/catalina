import math
from collections.abc import Sequence
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from catalina_ingestion.clients.ollama import (
    get_ollama_client,
)
from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.domain.embeddings import (
    EmbeddedChunk,
    EmbeddedDocument,
    EmbeddingStatistics,
    TextEmbeddingBatch,
)
from catalina_ingestion.domain.exceptions import (
    EmbeddingError,
    TransientEmbeddingError,
)
from catalina_ingestion.domain.processed import DocumentChunk


class EmbeddingService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client

    async def generate(
        self,
        chunks: Sequence[DocumentChunk],
    ) -> EmbeddedDocument:
        if not chunks:
            raise EmbeddingError(
                "NO_CHUNKS_TO_EMBED",
                "El documento no contiene chunks para procesar.",
            )

        embedded_texts = await self.generate_texts([chunk.text for chunk in chunks])

        embedded_chunks = [
            EmbeddedChunk(
                chunk=chunk,
                vector=vector,
            )
            for chunk, vector in zip(
                chunks,
                embedded_texts.vectors,
                strict=True,
            )
        ]

        return EmbeddedDocument(
            model=embedded_texts.model,
            dimension=embedded_texts.dimension,
            chunks=embedded_chunks,
            statistics=embedded_texts.statistics,
        )

    async def generate_texts(
        self,
        texts: Sequence[str],
    ) -> TextEmbeddingBatch:
        if not texts:
            raise EmbeddingError(
                "NO_TEXTS_TO_EMBED",
                "No se proporcionaron textos para generar embeddings.",
            )

        for text_index, text in enumerate(texts):
            if not text.strip():
                raise EmbeddingError(
                    "EMPTY_TEXT_TO_EMBED",
                    "No se puede generar un embedding de un texto vacío.",
                    {"text_index": text_index},
                )

        client = self.client or get_ollama_client()
        vectors: list[tuple[float, ...]] = []

        total_duration_ns = 0
        load_duration_ns = 0
        prompt_eval_count = 0
        batch_count = 0

        for start in range(
            0,
            len(texts),
            self.settings.embedding_batch_size,
        ):
            batch = list(texts[start : start + self.settings.embedding_batch_size])

            batch_vectors, metrics = await self._request_with_retry(
                client=client,
                texts=batch,
                batch_number=batch_count,
            )

            vectors.extend(batch_vectors)
            total_duration_ns += metrics["total_duration"]
            load_duration_ns += metrics["load_duration"]
            prompt_eval_count += metrics["prompt_eval_count"]
            batch_count += 1

        return TextEmbeddingBatch(
            model=self.settings.ollama_embedding_model,
            dimension=self.settings.embedding_dimension,
            vectors=tuple(vectors),
            statistics=EmbeddingStatistics(
                batch_count=batch_count,
                input_count=len(vectors),
                total_duration_ns=total_duration_ns,
                load_duration_ns=load_duration_ns,
                prompt_eval_count=prompt_eval_count,
            ),
        )

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        texts: list[str],
        batch_number: int,
    ) -> tuple[
        list[tuple[float, ...]],
        dict[str, int],
    ]:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self.settings.embedding_retry_attempts),
            wait=wait_exponential(
                multiplier=(self.settings.embedding_retry_wait_seconds),
                min=self.settings.embedding_retry_wait_seconds,
                max=8,
            ),
            retry=retry_if_exception_type(TransientEmbeddingError),
            reraise=True,
        )

        async for attempt in retrying:
            with attempt:
                return await self._request_batch(
                    client=client,
                    texts=texts,
                    batch_number=batch_number,
                )

        raise RuntimeError("El ciclo de reintentos terminó sin resultado.")

    async def _request_batch(
        self,
        client: httpx.AsyncClient,
        texts: list[str],
        batch_number: int,
    ) -> tuple[
        list[tuple[float, ...]],
        dict[str, int],
    ]:
        try:
            response = await client.post(
                "/api/embed",
                json={
                    "model": (self.settings.ollama_embedding_model),
                    "input": texts,
                    "truncate": self.settings.ollama_truncate,
                    "keep_alive": (self.settings.ollama_keep_alive),
                },
            )
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
        ) as error:
            raise TransientEmbeddingError(
                "OLLAMA_CONNECTION_ERROR",
                "No fue posible comunicarse con Ollama.",
                {
                    "batch_number": batch_number,
                    "error_type": type(error).__name__,
                },
            ) from error

        if response.status_code == 429 or response.status_code >= 500:
            raise TransientEmbeddingError(
                "OLLAMA_TEMPORARY_ERROR",
                "Ollama presentó un error temporal.",
                {
                    "batch_number": batch_number,
                    "status_code": response.status_code,
                },
            )

        if response.status_code >= 400:
            raise EmbeddingError(
                "OLLAMA_REQUEST_REJECTED",
                "Ollama rechazó la solicitud de embeddings.",
                {
                    "batch_number": batch_number,
                    "status_code": response.status_code,
                },
            )

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as error:
            raise EmbeddingError(
                "INVALID_OLLAMA_RESPONSE",
                "Ollama devolvió una respuesta JSON inválida.",
                {"batch_number": batch_number},
            ) from error

        raw_embeddings = payload.get("embeddings")

        if not isinstance(raw_embeddings, list):
            raise EmbeddingError(
                "MISSING_EMBEDDINGS",
                "La respuesta de Ollama no contiene embeddings.",
                {"batch_number": batch_number},
            )

        if len(raw_embeddings) != len(texts):
            raise EmbeddingError(
                "EMBEDDING_COUNT_MISMATCH",
                "La cantidad de vectores no coincide con la cantidad de chunks enviados.",
                {
                    "batch_number": batch_number,
                    "expected": len(texts),
                    "received": len(raw_embeddings),
                },
            )

        vectors = [
            self._validate_vector(
                raw_vector,
                batch_number,
                vector_index,
            )
            for vector_index, raw_vector in enumerate(raw_embeddings)
        ]

        metrics = {
            "total_duration": int(payload.get("total_duration") or 0),
            "load_duration": int(payload.get("load_duration") or 0),
            "prompt_eval_count": int(payload.get("prompt_eval_count") or 0),
        }

        return vectors, metrics

    def _validate_vector(
        self,
        raw_vector: Any,
        batch_number: int,
        vector_index: int,
    ) -> tuple[float, ...]:
        if not isinstance(raw_vector, list):
            raise EmbeddingError(
                "INVALID_EMBEDDING",
                "Ollama devolvió un vector inválido.",
                {
                    "batch_number": batch_number,
                    "vector_index": vector_index,
                },
            )

        try:
            vector = tuple(float(value) for value in raw_vector)
        except (TypeError, ValueError) as error:
            raise EmbeddingError(
                "NON_NUMERIC_EMBEDDING",
                "El vector contiene valores no numéricos.",
                {
                    "batch_number": batch_number,
                    "vector_index": vector_index,
                },
            ) from error

        if len(vector) != self.settings.embedding_dimension:
            raise EmbeddingError(
                "EMBEDDING_DIMENSION_MISMATCH",
                "La dimensión recibida no coincide con la configuración de Catalina.",
                {
                    "batch_number": batch_number,
                    "vector_index": vector_index,
                    "expected": (self.settings.embedding_dimension),
                    "received": len(vector),
                },
            )

        if not all(math.isfinite(value) for value in vector):
            raise EmbeddingError(
                "NON_FINITE_EMBEDDING",
                "El vector contiene valores infinitos o NaN.",
                {
                    "batch_number": batch_number,
                    "vector_index": vector_index,
                },
            )

        vector_norm = math.sqrt(sum(value * value for value in vector))

        if vector_norm == 0:
            raise EmbeddingError(
                "ZERO_EMBEDDING",
                "Ollama devolvió un vector compuesto por ceros.",
                {
                    "batch_number": batch_number,
                    "vector_index": vector_index,
                },
            )

        return vector
