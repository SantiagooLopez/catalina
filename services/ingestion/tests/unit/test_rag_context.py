import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.domain.evidence import EvidencePolicy
from catalina_ingestion.domain.retrieval import RetrievalQuery, RetrievedChunk
from catalina_ingestion.domain.selection import SelectedSearchResult
from catalina_ingestion.services.evidence import assess_evidence
from catalina_ingestion.services.grounding import GroundingGuard
from catalina_ingestion.services.rag_context import (
    ContextBuilder,
    RagContextService,
)


def chunk(point_id="p1", text="Información institucional.", score=0.90):
    return RetrievedChunk(
        point_id=point_id,
        score=score,
        text=text,
        document_id=1,
        document_version_id=1,
        document_name="Guía institucional",
        version="1.0.0",
        category="faq",
        language="es",
        page_start=None,
        page_end=None,
        section=None,
        chunk_index=0,
        text_sha256="a" * 64,
        content_sha256="b" * 64,
        embedding_model="embeddinggemma:latest",
        metadata={"index_run_id": "08f11af8-3950-4bd6-8b25-1f54df798a3e"},
    )


def evidence(
    *chunks,
    policy=None,
    query="Consulta institucional",
):
    selected = SelectedSearchResult(
        query=query,
        chunks=tuple(chunks),
        candidate_count=len(chunks),
        removed_by_threshold=0,
        removed_by_top_k=0,
    )
    return assess_evidence(
        selected,
        policy=policy or EvidencePolicy(minimum_characters=1),
    )


def test_builds_context_with_traceable_sources():
    result = ContextBuilder().build(
        evidence(
            chunk("p1", "Texto uno."),
            chunk("p2", "Texto dos.", 0.85),
        )
    )

    payload = json.loads(result.text)

    assert result.enabled is True
    assert result.reason == "ready"
    assert [source.citation_id for source in result.sources] == ["S1", "S2"]
    assert payload["sources"][0]["text"] == "Texto uno."
    assert payload["sources"][1]["source"]["point_id"] == "p2"
    assert result.sources[0].document_version_id == 1
    assert result.sources[0].page_start is None
    assert result.character_count == len(result.text)


def test_does_not_enable_context_for_rejected_evidence():
    result = ContextBuilder().build(evidence(chunk(score=0.29)))

    assert result.enabled is False
    assert result.reason == "insufficient_evidence"
    assert result.text == ""
    assert result.sources == ()


def test_accepts_context_exactly_at_budget():
    source = evidence(chunk())
    complete = ContextBuilder().build(source)

    result = ContextBuilder(max_context_characters=complete.character_count).build(source)

    assert result.enabled is True
    assert result.text == complete.text


def test_rejects_when_no_complete_chunk_fits():
    source = evidence(chunk())
    complete = ContextBuilder().build(source)

    result = ContextBuilder(max_context_characters=complete.character_count - 1).build(source)

    assert result.enabled is False
    assert result.reason == "insufficient_evidence_after_budget"
    assert result.omitted_by_budget == 1
    assert result.text == ""


def test_can_skip_large_chunk_and_keep_next_complete_chunk():
    small = chunk("p2", "Texto breve.", 0.85)
    budget = ContextBuilder().build(evidence(small)).character_count

    result = ContextBuilder(budget).build(
        evidence(
            chunk("p1", "Información extensa. " * 500),
            small,
        )
    )

    assert result.enabled is True
    assert result.omitted_by_budget == 1
    assert len(result.sources) == 1
    assert result.sources[0].citation_id == "S1"
    assert result.sources[0].point_id == "p2"


def test_rechecks_minimum_chunks_after_budget():
    first = chunk("p1", "Texto uno.")
    second = chunk("p2", "Texto dos.", 0.85)

    budget = ContextBuilder().build(evidence(first)).character_count

    source = evidence(
        first,
        second,
        policy=EvidencePolicy(
            minimum_characters=1,
            minimum_chunks=2,
        ),
    )

    assert source.assessment.evidence_sufficient is True

    result = ContextBuilder(budget).build(source)

    assert result.enabled is False
    assert result.reason == "insufficient_evidence_after_budget"
    assert result.sources == ()


def test_preserves_document_text_as_json_data():
    text = 'Texto con "comillas", saltos\n y {"sources": "falso"}'
    result = ContextBuilder().build(evidence(chunk(text=text)))

    payload = json.loads(result.text)

    assert payload["sources"][0]["text"] == text
    assert len(payload["sources"]) == 1


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_rejects_invalid_budget(budget):
    with pytest.raises(ValueError):
        ContextBuilder(budget)


@pytest.mark.asyncio
async def test_propagates_retrieval_failure():
    service = RagContextService(
        evidence_service=SimpleNamespace(
            search=AsyncMock(side_effect=RuntimeError("Fallo de recuperación"))
        )
    )

    with pytest.raises(RuntimeError, match="Fallo de recuperación"):
        await service.build(RetrievalQuery(query="Consulta"))


def test_grounding_rejects_missing_year():
    result = ContextBuilder().build(
        evidence(
            chunk(text=("Calendario académico de pregrado para el año 2026.")),
            query=("¿Cuál es el calendario académico para 2027?"),
        ),
        grounding_guard=GroundingGuard(),
    )

    assert result.enabled is False
    assert result.reason == "unsupported_grounding"
    assert result.text == ""
    assert result.sources == ()
    assert result.grounding is not None
    assert result.grounding.reasons == ("missing_year:2027",)


def test_grounding_accepts_supported_year():
    result = ContextBuilder().build(
        evidence(
            chunk(text=("Calendario académico de pregrado para el año 2026.")),
            query=("¿Cuál es el calendario académico para 2026?"),
        ),
        grounding_guard=GroundingGuard(),
    )

    assert result.enabled is True
    assert result.reason == "ready"
    assert result.grounding is not None
    assert result.grounding.supported is True
    assert result.grounding.reasons == ("passed_grounding_checks",)


@pytest.mark.asyncio
async def test_rag_service_applies_grounding_guard():
    source = evidence(
        chunk(text=("Las sedes institucionales se encuentran en Bogotá.")),
        query=("¿Dónde queda la sede en Cali?"),
    )

    evidence_service = SimpleNamespace(search=AsyncMock(return_value=source))

    service = RagContextService(
        evidence_service=evidence_service,
        grounding_guard=GroundingGuard(),
    )

    query = RetrievalQuery(query="¿Dónde queda la sede en Cali?")

    result = await service.build(query)

    assert result.enabled is False
    assert result.reason == "unsupported_grounding"
    assert result.grounding is not None
    assert result.grounding.reasons == ("missing_location:cali",)

    evidence_service.search.assert_awaited_once_with(query)


@pytest.mark.asyncio
async def test_rag_service_preserves_old_behavior_without_guard():
    source = evidence(
        chunk(text=("Las sedes institucionales se encuentran en Bogotá.")),
        query=("¿Dónde queda la sede en Cali?"),
    )

    evidence_service = SimpleNamespace(search=AsyncMock(return_value=source))

    service = RagContextService(evidence_service=evidence_service)

    result = await service.build(RetrievalQuery(query=("¿Dónde queda la sede en Cali?")))

    assert result.enabled is True
    assert result.reason == "ready"
    assert result.grounding is None
