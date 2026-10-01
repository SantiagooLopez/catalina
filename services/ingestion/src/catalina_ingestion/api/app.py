from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from catalina_ingestion.api.errors import (
    authentication_error_handler,
    generation_error_handler,
    retrieval_error_handler,
    unexpected_error_handler,
)
from catalina_ingestion.api.routes.answers import (
    router as answers_router,
)
from catalina_ingestion.api.routes.auth import (
    router as auth_router,
)
from catalina_ingestion.api.routes.health import (
    router as health_router,
)
from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.clients.qdrant import (
    close_qdrant_client,
    open_qdrant_client,
)
from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
)
from catalina_ingestion.domain.exceptions import (
    AuthenticationError,
    GenerationError,
)
from catalina_ingestion.domain.retrieval_runtime import (
    RetrievalExecutionError,
)
from catalina_ingestion.services.answer_generation import (
    AnswerGenerationService,
)
from catalina_ingestion.services.auth import (
    AuthService,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        app.state.answer_service = AnswerGenerationService()
        app.state.auth_service = AuthService()
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Catalina API",
        description=("API del agente virtual institucional Catalina."),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(
        health_router,
        prefix="/api/v1",
    )

    app.include_router(
        answers_router,
        prefix="/api/v1",
    )
    app.include_router(
        auth_router,
        prefix="/api/v1",
    )
    app.add_exception_handler(
        RetrievalExecutionError,
        retrieval_error_handler,
    )

    app.add_exception_handler(
        GenerationError,
        generation_error_handler,
    )

    app.add_exception_handler(
        AuthenticationError,
        authentication_error_handler,
    )

    app.add_exception_handler(
        Exception,
        unexpected_error_handler,
    )

    return app


app = create_app()
