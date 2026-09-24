from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from catalina_ingestion.domain.evidence import (
    EvidenceAssessment,
    EvidencePolicy,
    EvidenceReason,
)
from catalina_ingestion.domain.exceptions import GenerationError
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationPrompt,
    GenerationReason,
    GenerationStatistics,
)
from catalina_ingestion.domain.rag_context import (
    ContextSource,
    RagContext,
)
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.answer_generation import (
    AnswerGenerationService,
)


def make_assessment() -> EvidenceAssessment:
    return EvidenceAssessment(
        evidence_sufficient=True,
        reasons=(EvidenceReason.PASSED_RETRIEVAL_CHECKS,),
        evaluated_chunks=1,
        relevant_chunks=1,
        document_count=1,
        character_count=100,
        best_score=0.90,
        policy=EvidencePolicy(
            minimum_characters=1,
        ),
    )


def make_source() -> ContextSource:
    return ContextSource(
        citation_id="S1",
        point_id="point-1",
        document_id=1,
        document_version_id=1,
        document_name="Documento institucional",
        version="1.0",
        page_start=1,
        page_end=1,
        section="Sección",
        index_run_id="run-1",
    )


def make_enabled_context() -> RagContext:
    source = make_source()

    return RagContext(
        query="¿Cuál es la información?",
        enabled=True,
        reason="ready",
        text='{"sources":[]}',
        sources=(source,),
        character_count=14,
        omitted_by_budget=0,
        assessment=make_assessment(),
    )


def make_disabled_context(
    reason: str,
) -> RagContext:
    return RagContext(
        query="Pregunta sin soporte",
        enabled=False,
        reason=reason,
        text="",
        sources=(),
        character_count=0,
        omitted_by_budget=0,
        assessment=make_assessment(),
    )


@pytest.mark.asyncio
async def test_generates_answer_when_context_is_enabled():
    context = make_enabled_context()

    retrieval_service = SimpleNamespace(build=AsyncMock(return_value=context))

    prompt = GenerationPrompt(
        system_message="Sistema",
        user_message="Usuario",
        allowed_citations=("S1",),
    )

    prompt_builder = Mock()
    prompt_builder.build.return_value = prompt

    generated = GeneratedAnswer(
        query=context.query,
        text="Respuesta institucional. [S1]",
        generated=True,
        reason=GenerationReason.GENERATED,
        model="llama3.2:3b",
        citations=context.sources,
        statistics=GenerationStatistics(
            total_duration_ns=100,
            load_duration_ns=10,
            prompt_eval_count=20,
            prompt_eval_duration_ns=30,
            eval_count=10,
            eval_duration_ns=40,
        ),
    )

    generation_service = SimpleNamespace(generate=AsyncMock(return_value=generated))

    service = AnswerGenerationService(
        retrieval_service=retrieval_service,
        prompt_builder=prompt_builder,
        generation_service=generation_service,
    )

    query = RetrievalQuery(query="¿Cuál es la información?")

    result = await service.answer(query)

    assert result is generated

    retrieval_service.build.assert_awaited_once_with(query)

    prompt_builder.build.assert_called_once_with(context)

    generation_service.generate.assert_awaited_once_with(
        query=context.query,
        prompt=prompt,
        citations=context.sources,
    )


@pytest.mark.parametrize(
    ("context_reason", "expected_reason"),
    (
        (
            "insufficient_evidence",
            GenerationReason.INSUFFICIENT_EVIDENCE,
        ),
        (
            "insufficient_evidence_after_budget",
            GenerationReason.INSUFFICIENT_EVIDENCE_AFTER_BUDGET,
        ),
        (
            "unsupported_grounding",
            GenerationReason.UNSUPPORTED_GROUNDING,
        ),
    ),
)
@pytest.mark.asyncio
async def test_does_not_call_llm_when_context_is_disabled(
    context_reason,
    expected_reason,
):
    context = make_disabled_context(context_reason)

    retrieval_service = SimpleNamespace(build=AsyncMock(return_value=context))

    prompt_builder = Mock()

    generation_service = SimpleNamespace(generate=AsyncMock())

    service = AnswerGenerationService(
        retrieval_service=retrieval_service,
        prompt_builder=prompt_builder,
        generation_service=generation_service,
    )

    result = await service.answer(RetrievalQuery(query="Pregunta sin soporte"))

    assert result.generated is False
    assert result.reason is expected_reason
    assert result.model is None
    assert result.statistics is None
    assert result.citations == ()

    prompt_builder.build.assert_not_called()
    generation_service.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_unknown_disabled_context_reason():
    context = make_disabled_context("motivo_desconocido")

    retrieval_service = SimpleNamespace(build=AsyncMock(return_value=context))

    service = AnswerGenerationService(
        retrieval_service=retrieval_service,
        prompt_builder=Mock(),
        generation_service=SimpleNamespace(generate=AsyncMock()),
    )

    with pytest.raises(
        ValueError,
        match="Motivo de rechazo RAG no soportado",
    ):
        await service.answer(RetrievalQuery(query="Pregunta"))


@pytest.mark.asyncio
async def test_retries_once_when_generation_fails_verification():
    context = make_enabled_context()

    context = RagContext(
        query=("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?"),
        enabled=context.enabled,
        reason=context.reason,
        text=context.text,
        sources=(
            ContextSource(
                citation_id="S1",
                point_id="point-1",
                document_id=1,
                document_version_id=1,
                document_name=("Modificación del Calendario Académico de Pregrado 2026"),
                version="050-2026",
                page_start=1,
                page_end=1,
                section="Modificación",
                index_run_id="run-1",
            ),
        ),
        character_count=context.character_count,
        omitted_by_budget=context.omitted_by_budget,
        assessment=context.assessment,
    )

    retrieval_service = SimpleNamespace(build=AsyncMock(return_value=context))

    prompt = GenerationPrompt(
        system_message="Sistema",
        user_message="Pregunta y evidencia",
        allowed_citations=("S1",),
    )

    prompt_builder = Mock()
    prompt_builder.build.return_value = prompt

    wrong_answer = GeneratedAnswer(
        query=context.query,
        text="El acuerdo fue el Acuerdo 046 de 2025. [S1]",
        generated=True,
        reason=GenerationReason.GENERATED,
        model="llama3.2:3b",
        citations=context.sources,
        statistics=GenerationStatistics(
            total_duration_ns=100,
            load_duration_ns=10,
            prompt_eval_count=20,
            prompt_eval_duration_ns=30,
            eval_count=10,
            eval_duration_ns=40,
        ),
    )

    corrected_answer = GeneratedAnswer(
        query=context.query,
        text="El acuerdo fue el Acuerdo 050 de 2026. [S1]",
        generated=True,
        reason=GenerationReason.GENERATED,
        model="llama3.2:3b",
        citations=context.sources,
        statistics=GenerationStatistics(
            total_duration_ns=100,
            load_duration_ns=10,
            prompt_eval_count=20,
            prompt_eval_duration_ns=30,
            eval_count=10,
            eval_duration_ns=40,
        ),
    )

    generation_service = SimpleNamespace(
        generate=AsyncMock(
            side_effect=[
                wrong_answer,
                corrected_answer,
            ]
        )
    )

    service = AnswerGenerationService(
        retrieval_service=retrieval_service,
        prompt_builder=prompt_builder,
        generation_service=generation_service,
        identifier_resolver=SimpleNamespace(resolve=Mock(return_value=None)),
    )

    result = await service.answer(RetrievalQuery(query=context.query))

    assert result is corrected_answer
    assert generation_service.generate.await_count == 2

    second_call = generation_service.generate.await_args_list[1]

    correction_prompt = second_call.kwargs["prompt"]

    assert "050-2026" in correction_prompt.user_message
    assert "Acuerdo 046" in correction_prompt.user_message


@pytest.mark.asyncio
async def test_fails_after_single_unsuccessful_correction():
    context = make_enabled_context()

    context = RagContext(
        query=("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?"),
        enabled=context.enabled,
        reason=context.reason,
        text=context.text,
        sources=(
            ContextSource(
                citation_id="S1",
                point_id="point-1",
                document_id=1,
                document_version_id=1,
                document_name=("Modificación del Calendario Académico de Pregrado 2026"),
                version="050-2026",
                page_start=1,
                page_end=1,
                section="Modificación",
                index_run_id="run-1",
            ),
        ),
        character_count=context.character_count,
        omitted_by_budget=context.omitted_by_budget,
        assessment=context.assessment,
    )

    retrieval_service = SimpleNamespace(build=AsyncMock(return_value=context))

    prompt_builder = Mock()
    prompt_builder.build.return_value = GenerationPrompt(
        system_message="Sistema",
        user_message="Pregunta y evidencia",
        allowed_citations=("S1",),
    )

    wrong_answer = GeneratedAnswer(
        query=context.query,
        text="El acuerdo fue el Acuerdo 046 de 2025. [S1]",
        generated=True,
        reason=GenerationReason.GENERATED,
        model="llama3.2:3b",
        citations=context.sources,
        statistics=GenerationStatistics(
            total_duration_ns=100,
            load_duration_ns=10,
            prompt_eval_count=20,
            prompt_eval_duration_ns=30,
            eval_count=10,
            eval_duration_ns=40,
        ),
    )

    generation_service = SimpleNamespace(
        generate=AsyncMock(
            side_effect=[
                wrong_answer,
                wrong_answer,
            ]
        )
    )

    service = AnswerGenerationService(
        retrieval_service=retrieval_service,
        prompt_builder=prompt_builder,
        generation_service=generation_service,
        identifier_resolver=SimpleNamespace(resolve=Mock(return_value=None)),
    )

    with pytest.raises(GenerationError) as captured:
        await service.answer(RetrievalQuery(query=context.query))

    assert captured.value.code == "GENERATION_VERIFICATION_FAILED"

    assert generation_service.generate.await_count == 2


@pytest.mark.asyncio
async def test_resolves_document_identifier_without_llm():
    source = ContextSource(
        citation_id="S1",
        point_id="point-1",
        document_id=1,
        document_version_id=1,
        document_name=("Modificación del Calendario Académico de Pregrado 2026"),
        version="050-2026",
        page_start=1,
        page_end=1,
        section=("Por el cual se modifica el Calendario Académico"),
        index_run_id="run-1",
    )

    base_context = make_enabled_context()

    context = RagContext(
        query=("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?"),
        enabled=True,
        reason="ready",
        text=base_context.text,
        sources=(source,),
        character_count=base_context.character_count,
        omitted_by_budget=0,
        assessment=base_context.assessment,
    )

    retrieval_service = SimpleNamespace(build=AsyncMock(return_value=context))

    prompt_builder = Mock()

    generation_service = SimpleNamespace(generate=AsyncMock())

    service = AnswerGenerationService(
        retrieval_service=retrieval_service,
        prompt_builder=prompt_builder,
        generation_service=generation_service,
    )

    result = await service.answer(RetrievalQuery(query=context.query))

    assert result.generated is False
    assert result.reason is GenerationReason.DOCUMENT_IDENTIFIER_RESOLVED

    assert result.model is None
    assert result.statistics is None

    assert result.citations == (source,)

    assert "050-2026" in result.text
    assert "[S1]" in result.text

    prompt_builder.build.assert_not_called()
    generation_service.generate.assert_not_awaited()
