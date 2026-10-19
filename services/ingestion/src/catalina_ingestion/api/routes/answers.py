from typing import Annotated

from fastapi import (
    APIRouter,
    Request,
    Security,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from catalina_ingestion.domain.conversation_answers import (
    ConversationAnswerResult,
)
from catalina_ingestion.domain.exceptions import (
    InvalidAccessTokenError,
)
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationReason,
    GenerationStatistics,
)
from catalina_ingestion.domain.rag_context import (
    ContextSource,
)
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.auth import (
    AuthService,
)
from catalina_ingestion.services.conversation_answers import (
    ConversationAnswerService,
)

router = APIRouter(
    tags=["answers"],
)

bearer_scheme = HTTPBearer(
    auto_error=False,
)


class AnswerRequest(BaseModel):
    conversation_id: int = Field(
        gt=0,
    )

    query: str = Field(
        min_length=1,
        max_length=1000,
    )

    @field_validator("query")
    @classmethod
    def validate_query(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("La consulta no puede estar vacía.")

        return cleaned


class SourceResponse(BaseModel):
    citation_id: str
    point_id: str
    document_id: int
    document_version_id: int
    document_name: str
    version: str
    page_start: int | None
    page_end: int | None
    section: str | None
    index_run_id: str


class GuestAnswerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La consulta no puede estar vacía.")
        return value.strip()


class GuestAnswerResponse(BaseModel):
    query: str
    text: str
    citations: list[SourceResponse]
    generated: bool
    reason: GenerationReason
    model: str | None


@router.post("/guest/answers", response_model=GuestAnswerResponse)
async def guest_answer(payload: GuestAnswerRequest, request: Request) -> GuestAnswerResponse:
    # No account, conversation identifiers or personal history are exposed or persisted.
    service = request.app.state.answer_service
    result = await service.answer(RetrievalQuery(query=payload.query))
    return GuestAnswerResponse(
        query=result.query,
        text=result.text,
        citations=[_source_response(source) for source in result.citations],
        generated=result.generated,
        reason=result.reason,
        model=result.model,
    )


class GenerationStatisticsResponse(BaseModel):
    total_duration_ns: int
    load_duration_ns: int
    prompt_eval_count: int
    prompt_eval_duration_ns: int
    eval_count: int
    eval_duration_ns: int


class AnswerResponse(BaseModel):
    conversation_id: int
    message_id: int
    query: str
    text: str
    generated: bool
    reason: GenerationReason
    model: str | None
    citations: list[SourceResponse]
    statistics: GenerationStatisticsResponse | None


def _get_auth_service(
    request: Request,
) -> AuthService:
    service = getattr(
        request.app.state,
        "auth_service",
        None,
    )

    if service is None:
        raise RuntimeError("AuthService no ha sido inicializado.")

    return service


def _get_conversation_answer_service(
    request: Request,
) -> ConversationAnswerService:
    service = getattr(
        request.app.state,
        "conversation_answer_service",
        None,
    )

    if service is None:
        raise RuntimeError("ConversationAnswerService no ha sido inicializado.")

    return service


def _source_response(
    source: ContextSource,
) -> SourceResponse:
    return SourceResponse(
        citation_id=source.citation_id,
        point_id=source.point_id,
        document_id=source.document_id,
        document_version_id=(source.document_version_id),
        document_name=source.document_name,
        version=source.version,
        page_start=source.page_start,
        page_end=source.page_end,
        section=source.section,
        index_run_id=source.index_run_id,
    )


def _statistics_response(
    statistics: GenerationStatistics | None,
) -> GenerationStatisticsResponse | None:
    if statistics is None:
        return None

    return GenerationStatisticsResponse(
        total_duration_ns=(statistics.total_duration_ns),
        load_duration_ns=(statistics.load_duration_ns),
        prompt_eval_count=(statistics.prompt_eval_count),
        prompt_eval_duration_ns=(statistics.prompt_eval_duration_ns),
        eval_count=statistics.eval_count,
        eval_duration_ns=(statistics.eval_duration_ns),
    )


def build_answer_response(
    result: ConversationAnswerResult,
) -> AnswerResponse:
    answer: GeneratedAnswer = result.answer

    return AnswerResponse(
        conversation_id=(result.message.conversacion_id),
        message_id=result.message.id,
        query=answer.query,
        text=answer.text,
        generated=answer.generated,
        reason=answer.reason,
        model=answer.model,
        citations=[_source_response(source) for source in answer.citations],
        statistics=_statistics_response(answer.statistics),
    )


@router.post(
    "/answers",
    response_model=AnswerResponse,
)
async def answer(
    payload: AnswerRequest,
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
) -> AnswerResponse:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise InvalidAccessTokenError

    auth_service = _get_auth_service(request)

    user = await auth_service.get_current_user(
        access_token=(credentials.credentials),
    )

    service = _get_conversation_answer_service(request)

    result = await service.answer(
        user_id=user.id,
        conversation_id=(payload.conversation_id),
        query=payload.query,
    )

    return build_answer_response(result)
