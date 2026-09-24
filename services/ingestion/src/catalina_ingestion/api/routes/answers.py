from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationReason,
    GenerationStatistics,
)
from catalina_ingestion.domain.rag_context import ContextSource
from catalina_ingestion.domain.retrieval import RetrievalQuery

router = APIRouter(
    tags=["answers"],
)


class AnswerRequest(BaseModel):
    query: str = Field(min_length=1)

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


class GenerationStatisticsResponse(BaseModel):
    total_duration_ns: int
    load_duration_ns: int
    prompt_eval_count: int
    prompt_eval_duration_ns: int
    eval_count: int
    eval_duration_ns: int


class AnswerResponse(BaseModel):
    query: str
    text: str
    generated: bool
    reason: GenerationReason
    model: str | None
    citations: list[SourceResponse]
    statistics: GenerationStatisticsResponse | None


def _source_response(
    source: ContextSource,
) -> SourceResponse:
    return SourceResponse(
        citation_id=source.citation_id,
        point_id=source.point_id,
        document_id=source.document_id,
        document_version_id=source.document_version_id,
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
        total_duration_ns=statistics.total_duration_ns,
        load_duration_ns=statistics.load_duration_ns,
        prompt_eval_count=statistics.prompt_eval_count,
        prompt_eval_duration_ns=(statistics.prompt_eval_duration_ns),
        eval_count=statistics.eval_count,
        eval_duration_ns=statistics.eval_duration_ns,
    )


def build_answer_response(
    answer: GeneratedAnswer,
) -> AnswerResponse:
    return AnswerResponse(
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
) -> AnswerResponse:
    service = getattr(
        request.app.state,
        "answer_service",
        None,
    )

    if service is None:
        raise RuntimeError("AnswerGenerationService no ha sido inicializado.")

    result = await service.answer(
        RetrievalQuery(
            query=payload.query,
        )
    )

    return build_answer_response(result)
