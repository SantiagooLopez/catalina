import json
from dataclasses import asdict, replace

from test_prompt_builder import make_context

from catalina_ingestion.domain.generation import GenerationReason
from catalina_ingestion.services.document_overview import resolve_overview


def test_extracts_actual_topics_with_citations_without_inference():
    base = make_context()
    text = "\n".join([
        "CAPÍTULO I: ADMISIÓN", "CAPÍTULO II: DERECHOS", "CAPÍTULO III: MATRÍCULA",
        "CAPÍTULO IV: EVALUACIÓN",
    ])
    context = replace(
        base, query="De qué trata el reglamento estudiantil", text=json.dumps({"sources": [
            {"source": asdict(base.sources[0]), "text": text},
        ]}),
    )
    result = resolve_overview(context)
    assert result.reason is GenerationReason.DOCUMENT_OVERVIEW
    assert not result.generated and result.model is None
    assert "Admisión" in result.text and "Matrícula" in result.text
    assert result.text.count("[S1]") == 4
    assert "requisitos" in result.text


def test_does_not_make_up_a_summary_when_there_is_only_a_title():
    base = make_context()
    context = replace(base, query="Dime de qué trata el reglamento estudiantil")
    assert resolve_overview(context) is None


def test_deduplicates_split_chapter_titles_and_ignores_empty_heading():
    base = make_context()
    text = "\n".join([
        "CAPÍTULO I: ADMISIÓN", "CAPÍTULO I: ADMISIÓN Y REINGRESO",
        "CAPÍTULO II: :", "CAPÍTULO II: DERECHOS", "CAPÍTULO III: MATRÍCULA",
        "CAPÍTULO IV: EVALUACIÓN",
    ])
    context = replace(base, query="De qué trata el reglamento estudiantil", text=json.dumps({
        "sources": [{"source": asdict(base.sources[0]), "text": text}],
    }))
    result = resolve_overview(context)
    assert result.text.count("• ") == 4
    assert "Admisión y reingreso" in result.text
    assert "• :" not in result.text
