from catalina_ingestion.domain.evidence import (
    EvidenceAssessment,
    EvidencePolicy,
    EvidenceReason,
)
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
from catalina_ingestion.services.generation_verifier import (
    GenerationVerifier,
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
        document_name=("Modificación del Calendario Académico de Pregrado 2026"),
        version="050-2026",
        page_start=1,
        page_end=1,
        section="Modificación del calendario",
        index_run_id="run-1",
    )


def make_context(
    query: str,
) -> RagContext:
    source = make_source()

    return RagContext(
        query=query,
        enabled=True,
        reason="ready",
        text='{"sources":[]}',
        sources=(source,),
        character_count=100,
        omitted_by_budget=0,
        assessment=make_assessment(),
    )


def make_answer(
    context: RagContext,
    text: str,
) -> GeneratedAnswer:
    return GeneratedAnswer(
        query=context.query,
        text=text,
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


def test_accepts_required_primary_identifier():
    context = make_context("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?")

    answer = make_answer(
        context,
        "El acuerdo fue el Acuerdo 050 de 2026. [S1]",
    )

    result = GenerationVerifier().verify(
        context=context,
        answer=answer,
    )

    assert result.valid is True
    assert result.reason == "passed"
    assert result.required_identifier == "050-2026"
    assert result.primary_citation == "S1"


def test_rejects_wrong_document_identifier():
    context = make_context("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?")

    answer = make_answer(
        context,
        "El acuerdo fue el Acuerdo 046 de 2025. [S1]",
    )

    result = GenerationVerifier().verify(
        context=context,
        answer=answer,
    )

    assert result.valid is False
    assert result.reason == "missing_primary_identifier"
    assert result.required_identifier == "050-2026"
    assert result.primary_citation == "S1"


def test_does_not_require_identifier_for_normal_question():
    context = make_context("¿Cuándo se realizan las ceremonias de grado?")

    answer = make_answer(
        context,
        "Las ceremonias se realizan en las fechas indicadas. [S1]",
    )

    result = GenerationVerifier().verify(
        context=context,
        answer=answer,
    )

    assert result.valid is True
    assert result.reason == "passed"
    assert result.required_identifier is None


def test_builds_corrective_prompt_with_required_identifier():
    context = make_context("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?")

    answer = make_answer(
        context,
        "El acuerdo fue el Acuerdo 046 de 2025. [S1]",
    )

    verifier = GenerationVerifier()

    verification = verifier.verify(
        context=context,
        answer=answer,
    )

    original_prompt = GenerationPrompt(
        system_message="Sistema",
        user_message="Pregunta y evidencia",
        allowed_citations=("S1",),
    )

    corrected = verifier.build_correction_prompt(
        original_prompt=original_prompt,
        previous_answer=answer.text,
        verification=verification,
    )

    assert "050-2026" in corrected.user_message
    assert "Acuerdo 046" in corrected.user_message
    assert "[S1]" in corrected.user_message
    assert corrected.allowed_citations == ("S1",)
