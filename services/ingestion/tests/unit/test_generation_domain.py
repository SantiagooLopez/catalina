import pytest

from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationReason,
    GenerationStatistics,
)


def make_statistics() -> GenerationStatistics:
    return GenerationStatistics(
        total_duration_ns=100,
        load_duration_ns=10,
        prompt_eval_count=20,
        prompt_eval_duration_ns=30,
        eval_count=15,
        eval_duration_ns=40,
    )


def test_generation_statistics_accept_nonnegative_values() -> None:
    statistics = make_statistics()

    assert statistics.total_duration_ns == 100
    assert statistics.eval_count == 15


@pytest.mark.parametrize(
    "field_name",
    (
        "total_duration_ns",
        "load_duration_ns",
        "prompt_eval_count",
        "prompt_eval_duration_ns",
        "eval_count",
        "eval_duration_ns",
    ),
)
def test_generation_statistics_reject_negative_values(
    field_name: str,
) -> None:
    values = {
        "total_duration_ns": 100,
        "load_duration_ns": 10,
        "prompt_eval_count": 20,
        "prompt_eval_duration_ns": 30,
        "eval_count": 15,
        "eval_duration_ns": 40,
    }
    values[field_name] = -1

    with pytest.raises(ValueError):
        GenerationStatistics(**values)


def test_generated_answer_requires_nonempty_query() -> None:
    with pytest.raises(ValueError):
        GeneratedAnswer(
            query="   ",
            text="Respuesta",
            generated=True,
            reason=GenerationReason.GENERATED,
            model="llama3.2:3b",
            citations=(),
            statistics=make_statistics(),
        )


def test_generated_answer_requires_text() -> None:
    with pytest.raises(ValueError):
        GeneratedAnswer(
            query="Pregunta válida",
            text="",
            generated=True,
            reason=GenerationReason.GENERATED,
            model="llama3.2:3b",
            citations=(),
            statistics=make_statistics(),
        )


def test_generated_answer_requires_model() -> None:
    with pytest.raises(ValueError):
        GeneratedAnswer(
            query="Pregunta válida",
            text="Respuesta",
            generated=True,
            reason=GenerationReason.GENERATED,
            model=None,
            citations=(),
            statistics=make_statistics(),
        )


def test_generated_answer_requires_statistics() -> None:
    with pytest.raises(ValueError):
        GeneratedAnswer(
            query="Pregunta válida",
            text="Respuesta",
            generated=True,
            reason=GenerationReason.GENERATED,
            model="llama3.2:3b",
            citations=(),
            statistics=None,
        )


def test_non_generated_answer_rejects_model() -> None:
    with pytest.raises(ValueError):
        GeneratedAnswer(
            query="Pregunta sin evidencia",
            text="No existe evidencia suficiente.",
            generated=False,
            reason=GenerationReason.INSUFFICIENT_EVIDENCE,
            model="llama3.2:3b",
            citations=(),
        )


def test_non_generated_answer_is_valid_without_model() -> None:
    answer = GeneratedAnswer(
        query="Pregunta sin evidencia",
        text="No existe evidencia institucional suficiente.",
        generated=False,
        reason=GenerationReason.INSUFFICIENT_EVIDENCE,
        model=None,
        citations=(),
    )

    assert answer.generated is False
    assert answer.model is None
