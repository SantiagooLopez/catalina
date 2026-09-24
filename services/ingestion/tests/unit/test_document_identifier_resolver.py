from catalina_ingestion.domain.evidence import (
    EvidenceAssessment,
    EvidencePolicy,
    EvidenceReason,
)
from catalina_ingestion.domain.rag_context import (
    ContextSource,
    RagContext,
)
from catalina_ingestion.services.document_identifier_resolver import (
    DocumentIdentifierResolver,
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


def make_source(
    *,
    version: str = "050-2026",
    document_name: str = ("Modificación del Calendario Académico de Pregrado 2026"),
    section: str = ("Por el cual se modifica el Calendario Académico"),
) -> ContextSource:
    return ContextSource(
        citation_id="S1",
        point_id="point-1",
        document_id=1,
        document_version_id=1,
        document_name=document_name,
        version=version,
        page_start=1,
        page_end=1,
        section=section,
        index_run_id="run-1",
    )


def make_context(
    query: str,
    *,
    enabled: bool = True,
    source: ContextSource | None = None,
) -> RagContext:
    sources = (source or make_source(),) if source is not None or enabled else ()

    return RagContext(
        query=query,
        enabled=enabled,
        reason=("ready" if enabled else "insufficient_evidence"),
        text=('{"sources":[]}' if enabled else ""),
        sources=sources,
        character_count=100 if enabled else 0,
        omitted_by_budget=0,
        assessment=make_assessment(),
    )


def test_resolves_identifier_when_action_matches():
    context = make_context("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?")

    result = DocumentIdentifierResolver().resolve(context)

    assert result is not None
    assert result.identifier_kind == "acuerdo"
    assert result.identifier == "050-2026"
    assert result.citation_id == "S1"
    assert "modific" in result.matched_actions
    assert result.source.version == "050-2026"


def test_does_not_resolve_normal_information_question():
    context = make_context("¿Cuándo se realizan las ceremonias de grado?")

    result = DocumentIdentifierResolver().resolve(context)

    assert result is None


def test_does_not_resolve_when_action_does_not_match():
    context = make_context("¿Qué acuerdo derogó el calendario académico de pregrado de 2026?")

    result = DocumentIdentifierResolver().resolve(context)

    assert result is None


def test_does_not_resolve_without_identifier():
    context = make_context(
        "¿Qué acuerdo modificó el calendario académico de pregrado de 2026?",
        source=make_source(version=""),
    )

    result = DocumentIdentifierResolver().resolve(context)

    assert result is None


def test_does_not_resolve_disabled_context():
    context = make_context(
        "¿Qué acuerdo modificó el calendario académico de pregrado de 2026?",
        enabled=False,
    )

    result = DocumentIdentifierResolver().resolve(context)

    assert result is None
