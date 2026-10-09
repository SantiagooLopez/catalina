from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from catalina_ingestion.api.errors import (
    authentication_error_handler,
    conversation_not_found_error_handler,
    forbidden_error_handler,
    generation_error_handler,
    invalid_current_password_error_handler,
    retrieval_error_handler,
    unexpected_error_handler,
    user_not_found_error_handler,
)
from catalina_ingestion.api.routes.answers import (
    router as answers_router,
)
from catalina_ingestion.api.routes.auth import (
    router as auth_router,
)
from catalina_ingestion.api.routes.conversations import (
    router as conversations_router,
)
from catalina_ingestion.api.routes.health import (
    router as health_router,
)
from catalina_ingestion.api.routes.users import (
    router as users_router,
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
    ConversationNotFoundError,
    ForbiddenError,
    GenerationError,
    InvalidCurrentPasswordError,
    UserNotFoundError,
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
from catalina_ingestion.services.conversation_answers import (
    ConversationAnswerService,
)
from catalina_ingestion.services.conversations import (
    ConversationService,
)
from catalina_ingestion.services.users import (
    UserService,
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

        answer_service = AnswerGenerationService()

        app.state.answer_service = answer_service
        app.state.user_service = UserService()
        app.state.conversation_answer_service = ConversationAnswerService(
            answer_service=answer_service,
        )

        app.state.auth_service = AuthService()
        app.state.conversation_service = ConversationService()
        app.state.user_service = UserService()
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
    app.include_router(
        conversations_router,
        prefix="/api/v1",
    )
    app.include_router(
        users_router,
        prefix="/api/v1",
    )
    app.add_exception_handler(
        UserNotFoundError,
        user_not_found_error_handler,
    )

    app.add_exception_handler(
        ForbiddenError,
        forbidden_error_handler,
    )

    app.add_exception_handler(
        InvalidCurrentPasswordError,
        invalid_current_password_error_handler,
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
        ConversationNotFoundError,
        conversation_not_found_error_handler,
    )
    app.add_exception_handler(
        Exception,
        unexpected_error_handler,
    )

    return app


app = create_app()
