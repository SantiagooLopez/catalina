import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from test_answer_generation import make_disabled_context, make_enabled_context

from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationReason,
    GenerationStatistics,
)
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.answer_generation import AnswerGenerationService


@pytest.mark.asyncio
async def test_cached_answer_still_rechecks_evidence_and_cannot_outlive_active_document():
    context = make_enabled_context()
    changed = replace(context, text='{"sources":[], "revision":2}')
    retrieval = SimpleNamespace(build=AsyncMock(side_effect=[
        context, context, changed, make_disabled_context("insufficient_evidence"),
    ]))
    answer = GeneratedAnswer(
        query=context.query, text="Información respaldada. [S1]", generated=True,
        reason=GenerationReason.GENERATED, model="llama3.2:3b", citations=context.sources,
        statistics=GenerationStatistics(1, 1, 1, 1, 1, 1),
    )
    generation = SimpleNamespace(generate=AsyncMock(return_value=answer))
    service = AnswerGenerationService(
        retrieval_service=retrieval, generation_service=generation, prompt_builder=Mock(),
    )
    query = RetrievalQuery(query=context.query)
    await service.answer(query)
    await service.answer(query)
    assert generation.generate.await_count == 1
    await service.answer(query)
    assert generation.generate.await_count == 2
    result = await service.answer(query)
    assert result.reason is GenerationReason.INSUFFICIENT_EVIDENCE
    assert retrieval.build.await_count == 4


@pytest.mark.asyncio
async def test_generated_mode_really_calls_model_instead_of_using_extractive_overview():
    from dataclasses import asdict

    context = make_enabled_context()
    context = replace(context, query="Dime de qué trata el reglamento", text=json.dumps({
        "sources": [{"source": asdict(context.sources[0]), "text":
                     "CAPÍTULO I: ADMISIÓN\nCAPÍTULO II: DERECHOS\n"
                     "CAPÍTULO III: MATRÍCULA\nCAPÍTULO IV: EVALUACIÓN"}],
    }))
    answer = GeneratedAnswer(
        query=context.query, text="Respuesta del modelo. [S1]", generated=True,
        reason=GenerationReason.GENERATED, model="llama3.2:3b", citations=context.sources,
        statistics=GenerationStatistics(1, 1, 1, 1, 1, 1),
    )
    for mode in ("generated", "extractive"):
        generation = SimpleNamespace(generate=AsyncMock(return_value=answer))
        service = AnswerGenerationService(
            retrieval_service=SimpleNamespace(build=AsyncMock(return_value=context)),
            generation_service=generation, prompt_builder=Mock(), document_response_mode=mode,
        )
        result = await service.answer(RetrievalQuery(query=context.query))
        if mode == "generated":
            generation.generate.assert_awaited_once()
            assert result.reason is GenerationReason.GENERATED
        else:
            generation.generate.assert_not_awaited()
            assert result.reason is GenerationReason.DOCUMENT_OVERVIEW
