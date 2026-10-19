import json
from dataclasses import asdict, replace

from test_prompt_builder import make_context

from catalina_ingestion.domain.generation import GenerationReason
from catalina_ingestion.services.document_excerpt import resolve_excerpt


def test_literal_lookup_preserves_condition_and_negation_verbatim():
    base = make_context()
    passage = (
        "Artículo 60. Faltas leves. Se consideran faltas leves aquellas relacionadas con "
        "el incumplimiento de los deberes del estudiante y que no se encuentran expresamente "
        "señaladas como faltas graves. Asimismo, constituyen faltas leves el incumplimiento "
        "de otras disposiciones debidamente aprobadas y divulgadas por la Universidad."
    )
    context = replace(base, query="¿Qué dice el reglamento sobre las faltas?", text=json.dumps({
        "sources": [{"source": asdict(base.sources[0]), "text": passage}],
    }))
    result = resolve_excerpt(context)
    assert result.reason is GenerationReason.DOCUMENT_EXCERPT
    assert passage in result.text
    assert not result.generated
    assert "no violan" not in result.text


def test_requests_for_explanation_still_use_generation():
    base = make_context()
    assert resolve_excerpt(replace(base, query="Explícame las faltas con ejemplos")) is None


def test_literal_lookup_without_useful_passage_falls_back_to_generation():
    base = make_context()
    assert resolve_excerpt(replace(base, query="¿Qué dice el reglamento sobre faltas?")) is None


def test_rights_lookup_returns_actual_items_instead_of_only_the_article_heading():
    base = make_context()
    items = [f"{i}. Recibir información y orientación institucional sobre el tema {i}."
             for i in range(1, 18)]
    passage = "Artículo 5. Derechos Son derechos de los estudiantes:\n\n" + " ".join(items)
    context = replace(base, query="¿Qué derechos tienen los estudiantes?", text=json.dumps({
        "sources": [{"source": asdict(base.sources[0]), "text": passage}],
    }))
    result = resolve_excerpt(context)
    assert items[0] in result.text and items[4] in result.text
    assert items[5] not in result.text
