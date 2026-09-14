import asyncio
import logging
from time import perf_counter
from uuid import uuid4

import httpx
from psycopg import InterfaceError, OperationalError
from psycopg_pool import PoolTimeout
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)

from catalina_ingestion.domain.exceptions import (
    EmbeddingError,
    TransientEmbeddingError,
)
from catalina_ingestion.domain.rag_context import RagContext
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.domain.retrieval_runtime import (
    RetrievalExecutionError,
    RetrievalRuntimePolicy,
)
from catalina_ingestion.domain.search import SearchError
from catalina_ingestion.services.action_anchor_reranker import (
    ActionAnchorReranker,
)
from catalina_ingestion.services.evidence import EvidenceRetrievalService
from catalina_ingestion.services.grounding import GroundingGuard
from catalina_ingestion.services.rag_context import RagContextService
from catalina_ingestion.services.retrieval_selection import (
    RetrievalSelectionService,
    validate_selection_query,
)

logger = logging.getLogger(__name__)

INPUT_ERROR_CODES = {
    "INVALID_QUERY_TYPE",
    "QUERY_TOO_LONG",
    "INVALID_QUERY_CHARACTER",
    "EMPTY_QUERY",
}


def classify_failure(error: Exception) -> tuple[str, str, bool]:
    if isinstance(error, TransientEmbeddingError):
        return (
            "EMBEDDING_UNAVAILABLE",
            "El servicio de embeddings no está disponible temporalmente.",
            True,
        )

    if isinstance(error, EmbeddingError):
        if error.code in INPUT_ERROR_CODES:
            return (
                "INVALID_QUERY",
                "La consulta no cumple los requisitos de entrada.",
                False,
            )

        return (
            "EMBEDDING_FAILED",
            "No fue posible generar un embedding válido.",
            False,
        )

    if isinstance(error, SearchError):
        return (
            "RETRIEVAL_DATA_ERROR",
            "Los datos de recuperación no cumplen el contrato esperado.",
            False,
        )

    if isinstance(error, (PoolTimeout, OperationalError, InterfaceError)):
        return (
            "DATABASE_UNAVAILABLE",
            "No fue posible consultar la base de datos.",
            True,
        )

    if isinstance(error, UnexpectedResponse):
        status = error.status_code
        retryable = status in (408, 429) or status >= 500

        return (
            "QDRANT_REQUEST_FAILED",
            "Qdrant rechazó o no pudo completar la búsqueda.",
            retryable,
        )

    if isinstance(error, ResponseHandlingException):
        original = getattr(error, "source", None)

        return (
            "QDRANT_RESPONSE_FAILED",
            "No fue posible obtener una respuesta válida de Qdrant.",
            isinstance(original, httpx.TransportError),
        )

    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return (
            "DEPENDENCY_TIMEOUT",
            "Un servicio excedió su tiempo de espera.",
            True,
        )

    if isinstance(error, httpx.TransportError):
        return (
            "DEPENDENCY_UNAVAILABLE",
            "No fue posible comunicarse con un servicio.",
            True,
        )

    return (
        "RETRIEVAL_INTERNAL_ERROR",
        "Ocurrió un error interno durante la recuperación.",
        False,
    )


class ManagedRetrievalService:
    def __init__(
        self,
        context_service: RagContextService | None = None,
        policy: RetrievalRuntimePolicy | None = None,
    ) -> None:
        if context_service is None:
            selection_service = RetrievalSelectionService(
                reranker=ActionAnchorReranker(
                    bonus=0.15,
                )
            )

            evidence_service = EvidenceRetrievalService(
                selection_service=selection_service,
            )

            context_service = RagContextService(
                evidence_service=evidence_service,
                grounding_guard=GroundingGuard(),
            )

        self.context_service = context_service
        self.policy = policy or RetrievalRuntimePolicy()
        self._active = 0

    async def build(self, query: RetrievalQuery) -> RagContext:
        request_id = str(uuid4())

        try:
            if not isinstance(query, RetrievalQuery):
                raise ValueError("Se esperaba RetrievalQuery.")

            if not isinstance(query.query, str) or not query.query.strip():
                raise ValueError("La consulta debe contener texto.")

            validate_selection_query(query)
        except ValueError as error:
            raise RetrievalExecutionError(
                "INVALID_QUERY",
                "La consulta no cumple los requisitos de entrada.",
                retryable=False,
                request_id=request_id,
            ) from error

        # No hay await entre la comprobación y el incremento.
        # Este contador pertenece a una instancia y un event loop.
        if self._active >= self.policy.max_concurrent:
            raise RetrievalExecutionError(
                "RETRIEVAL_BUSY",
                "El servicio está ocupado. Intenta nuevamente más tarde.",
                retryable=True,
                request_id=request_id,
            )

        self._active += 1
        started = perf_counter()
        deadline = asyncio.timeout(self.policy.timeout_seconds)

        try:
            async with deadline:
                result = await self.context_service.build(query)

            logger.info(
                "retrieval_completed request_id=%s elapsed_ms=%.1f enabled=%s",
                request_id,
                (perf_counter() - started) * 1000,
                result.enabled,
            )

            return result

        except asyncio.CancelledError:
            logger.info(
                "retrieval_cancelled request_id=%s",
                request_id,
            )
            raise

        except Exception as error:
            if deadline.expired():
                code = "RETRIEVAL_TIMEOUT"
                message = "La recuperación excedió el tiempo máximo permitido."
                retryable = True
            else:
                code, message, retryable = classify_failure(error)

            logger.warning(
                "retrieval_failed request_id=%s code=%s error_type=%s",
                request_id,
                code,
                type(error).__name__,
            )

            raise RetrievalExecutionError(
                code,
                message,
                retryable=retryable,
                request_id=request_id,
            ) from error

        finally:
            self._active -= 1
