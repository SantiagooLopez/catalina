import json
from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_prompt_builder import make_context

from catalina_ingestion.domain.search import SearchError
from catalina_ingestion.services import evidence_expansion as module

RUN = "58e2f18b-90cd-49fb-9bab-788f885725d7"


def setup(monkeypatch, texts, *, overview=True):
    base = make_context()
    source = replace(base.sources[0], index_run_id=RUN)
    context = replace(
        base, query="Dime de qué trata el reglamento estudiantil" if overview else
        "¿Qué derechos establece el reglamento?", sources=(source,),
        text=json.dumps({"sources": [{"source": asdict(source), "text": "DERECHOS"}]}),
    )
    points = []
    for index, text in enumerate(texts):
        points.append(SimpleNamespace(id=f"point-{index}", payload={
            **asdict(source), "schema_version": 1, "text": text,
            "chunk_index": index, "category": "reglamentos", "language": "es",
            "embedding_model": "embeddinggemma:latest", "metadata": {},
            "text_sha256": "a" * 64, "content_sha256": "b" * 64,
        }))
    client = SimpleNamespace(scroll=AsyncMock(return_value=(points, None)))
    repo = SimpleNamespace(active_runs=AsyncMock(return_value={RUN: (1, 1)}))
    monkeypatch.setattr(module, "get_qdrant_client", lambda: client)
    monkeypatch.setattr(module, "RetrievalRepository", lambda: repo)
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(
        ollama_embedding_model="embeddinggemma:latest", qdrant_collection="documents",
    ))
    return context, client, repo


@pytest.mark.asyncio
async def test_overview_uses_actual_chapters_and_cites_original_points(monkeypatch):
    context, client, _ = setup(monkeypatch, [
        "CAPÍTULO I: ADMISIÓN ........ 7\nCAPÍTULO II: DERECHOS Y DEBERES .... 11",
        "CAPÍTULO III: MATRÍCULA .... 12\nArtículo 20. Requisitos",
    ])
    result = await module.EvidenceExpansionService().expand(context)
    records = json.loads(result.text)["sources"]
    assert "ADMISIÓN" in records[0]["text"]
    assert "Artículo 20" not in records[1]["text"]
    assert result.sources[0].point_id == "point-0"
    scope = client.scroll.await_args.kwargs["scroll_filter"]
    assert {rule.key for rule in scope.must} == {
        "document_id", "document_version_id", "index_run_id", "embedding_model",
    }


@pytest.mark.asyncio
async def test_expansion_rejects_stale_document_before_reading(monkeypatch):
    context, client, repo = setup(monkeypatch, [])
    repo.active_runs.return_value = {}
    result = await module.EvidenceExpansionService().expand(context)
    assert not result.enabled and not result.sources
    client.scroll.assert_not_awaited()


@pytest.mark.asyncio
async def test_expansion_rechecks_document_version_after_reading(monkeypatch):
    context, _, repo = setup(monkeypatch, ["CAPÍTULO I: ADMISIÓN"])
    repo.active_runs.side_effect = [{RUN: (1, 1)}, {}]
    assert not (await module.EvidenceExpansionService().expand(context)).enabled


@pytest.mark.asyncio
async def test_expansion_cannot_include_other_document(monkeypatch):
    context, client, _ = setup(monkeypatch, ["CAPÍTULO I: ADMISIÓN"])
    client.scroll.return_value[0][0].payload["document_id"] = 999
    with pytest.raises(SearchError):
        await module.EvidenceExpansionService().expand(context)


@pytest.mark.asyncio
async def test_specific_question_uses_body_on_matched_page(monkeypatch):
    body = "El estudiante tiene derecho a conocer sus evaluaciones y recibir orientación. " * 3
    context, _, _ = setup(monkeypatch, ["DERECHOS", body], overview=False)
    result = await module.EvidenceExpansionService().expand(context)
    assert body.strip() in result.text
    assert '"text": "DERECHOS"' not in result.text


def test_summary_prompt_requires_substantive_structure():
    from catalina_ingestion.services.prompt_builder import PromptBuilder

    instruction = PromptBuilder._answer_instruction("Dime de qué trata el reglamento estudiantil")
    assert "4 y 6 puntos" in instruction
    assert "una sola oración" in instruction


@pytest.mark.parametrize("question", [
    "Resume las faltas del reglamento", "Explícame el artículo 60", "Resume los derechos",
])
def test_specific_legal_topic_is_not_a_whole_document_overview(question):
    assert not module.is_overview(question)


@pytest.mark.asyncio
async def test_prefers_first_complete_article_over_repeated_header_on_continuation(monkeypatch):
    rights = "Artículo 5. Derechos\n\n" + "1. Recibir un trato respetuoso de la comunidad. " * 3
    duties = "Artículo 5. Derechos\n\n" + "1. Acatar y cumplir los deberes establecidos. " * 3
    context, _, _ = setup(monkeypatch, [rights, duties], overview=False)
    result = await module.EvidenceExpansionService().expand(context)
    assert "Recibir un trato respetuoso" in result.text
    assert "Acatar y cumplir" not in result.text
