from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from catalina_ingestion.domain.exceptions import (
    AuthenticationError,
    ConversationNotFoundError,
    GenerationError,
    TransientGenerationError,
)
from catalina_ingestion.domain.retrieval_runtime import (
    RetrievalExecutionError,
)

GENERATION_UPSTREAM_CODES = {
    "OLLAMA_GENERATION_REJECTED",
    "INVALID_OLLAMA_GENERATION_RESPONSE",
    "UNEXPECTED_GENERATION_MODEL",
    "INCOMPLETE_GENERATION",
    "MISSING_GENERATION_MESSAGE",
    "INVALID_GENERATION_ROLE",
    "EMPTY_GENERATION_RESPONSE",
    "INVALID_GENERATION_METRIC",
    "MISSING_GENERATION_CITATION",
    "UNKNOWN_GENERATION_CITATION",
    "GENERATION_VERIFICATION_FAILED",
}


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
    request_id: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = {
        "X-Request-ID": request_id,
    }

    if headers is not None:
        response_headers.update(headers)

    return JSONResponse(
        status_code=status_code,
        headers=response_headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "request_id": request_id,
            }
        },
    )


def _retrieval_status(
    error: RetrievalExecutionError,
) -> int:
    if error.code == "INVALID_QUERY":
        return 400

    if error.code in {
        "RETRIEVAL_TIMEOUT",
        "DEPENDENCY_TIMEOUT",
    }:
        return 504

    if error.code == "RETRIEVAL_BUSY":
        return 503

    if error.retryable:
        return 503

    return 500


async def retrieval_error_handler(
    request: Request,
    error: RetrievalExecutionError,
) -> JSONResponse:
    del request

    return _error_response(
        status_code=_retrieval_status(error),
        code=error.code,
        message=str(error),
        retryable=error.retryable,
        request_id=error.request_id,
    )


def _generation_status(
    error: GenerationError,
) -> tuple[int, bool]:
    if isinstance(
        error,
        TransientGenerationError,
    ):
        return 503, True

    if error.code == "EMPTY_GENERATION_QUERY":
        return 400, False

    if error.code in GENERATION_UPSTREAM_CODES:
        return 502, False

    return 500, False


async def generation_error_handler(
    request: Request,
    error: GenerationError,
) -> JSONResponse:
    del request

    status_code, retryable = _generation_status(error)

    request_id = str(uuid4())

    return _error_response(
        status_code=status_code,
        code=error.code,
        message=error.message,
        retryable=retryable,
        request_id=request_id,
    )


async def authentication_error_handler(
    request: Request,
    error: AuthenticationError,
) -> JSONResponse:
    del request

    request_id = str(uuid4())

    return _error_response(
        status_code=401,
        code=error.code,
        message=error.message,
        retryable=False,
        request_id=request_id,
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


async def conversation_not_found_error_handler(
    request: Request,
    error: ConversationNotFoundError,
) -> JSONResponse:
    del request

    request_id = str(uuid4())

    return _error_response(
        status_code=404,
        code=error.code,
        message=error.message,
        retryable=False,
        request_id=request_id,
    )


async def unexpected_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request
    del error

    request_id = str(uuid4())

    return _error_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message=("Ocurrió un error interno procesando la solicitud."),
        retryable=False,
        request_id=request_id,
    )
