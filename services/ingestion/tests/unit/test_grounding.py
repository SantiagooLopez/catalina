import pytest

from catalina_ingestion.domain.grounding import (
    GroundingPolicy,
    GroundingReason,
)
from catalina_ingestion.domain.retrieval import RetrievedChunk
from catalina_ingestion.services.grounding import (
    GroundingGuard,
    assess_grounding,
)


def chunk(
    text: str,
    document_name: str = "Documento institucional",
):
    return RetrievedChunk(
        point_id="p1",
        score=0.90,
        text=text,
        document_id=1,
        document_version_id=1,
        document_name=document_name,
        version="1.0.0",
        category="faq",
        language="es",
        page_start=1,
        page_end=1,
        section=None,
        chunk_index=0,
        text_sha256="a" * 64,
        content_sha256="b" * 64,
        embedding_model="embeddinggemma:latest",
    )


def test_accepts_query_without_unsupported_anchors():
    result = assess_grounding(
        "¿Qué servicios ofrece Bienestar Universitario?",
        (chunk("Bienestar Universitario ofrece diversos servicios a estudiantes."),),
    )

    assert result.assessment.supported is True
    assert result.assessment.failures == ()
    assert result.assessment.reasons == (GroundingReason.PASSED_GROUNDING_CHECKS.value,)
    assert len(result.chunks) == 1


def test_rejects_missing_year():
    result = assess_grounding(
        "¿Cuál es el calendario académico para 2027?",
        (chunk("Calendario académico de pregrado para el año 2026."),),
    )

    assert result.assessment.supported is False
    assert result.assessment.reasons == ("missing_year:2027",)
    assert result.chunks == ()


def test_accepts_supported_year():
    result = assess_grounding(
        "¿Cuál es el calendario académico para 2026?",
        (chunk("Calendario académico de pregrado para el año 2026."),),
    )

    assert result.assessment.supported is True


def test_rejects_missing_location():
    result = assess_grounding(
        "¿Dónde queda la sede en Medellín?",
        (chunk("Las sedes institucionales están ubicadas en Bogotá D.C."),),
    )

    assert result.assessment.reasons == ("missing_location:medellin",)


def test_accepts_supported_location():
    result = assess_grounding(
        "¿Dónde queda la sede en Bogotá?",
        (chunk("La sede se encuentra en Bogotá D.C."),),
    )

    assert result.assessment.supported is True


def test_rejects_missing_service():
    result = assess_grounding(
        ("¿Bienestar Universitario ofrece servicio de odontología?"),
        (chunk("Bienestar Universitario ofrece actividades deportivas y culturales."),),
    )

    assert result.assessment.reasons == ("missing_service:odontologia",)


def test_rejects_missing_identifier():
    result = assess_grounding(
        "¿Cómo ingreso a PAW?",
        (chunk("El procedimiento se realiza mediante el portal institucional."),),
    )

    assert result.assessment.reasons == ("missing_identifier:paw",)


def test_accepts_supported_identifier():
    result = assess_grounding(
        "¿Cómo ingreso a PAW?",
        (chunk("Los estudiantes deben ingresar a PAW con sus credenciales."),),
    )

    assert result.assessment.supported is True


def test_rejects_unsupported_regulation_scope():
    result = assess_grounding(
        ("¿Qué establece el reglamento de profesores?"),
        (
            chunk(
                "El profesor participa en el procedimiento disciplinario.",
                document_name=("Reglamento del Estudiante"),
            ),
        ),
    )

    assert result.assessment.reasons == ("unsupported_regulation_scope:profesores",)


def test_accepts_supported_regulation_scope():
    result = assess_grounding(
        "¿Qué dice el reglamento del estudiante?",
        (
            chunk(
                "Reglamento institucional.",
                document_name=("Reglamento del Estudiante"),
            ),
        ),
    )

    assert result.assessment.supported is True


def test_does_not_require_exact_generic_verbs():
    result = assess_grounding(
        ("¿Qué acuerdo modificó el calendario académico de 2026?"),
        (chunk("Por el cual se modifica el Calendario Académico de 2026."),),
    )

    assert result.assessment.supported is True


def test_guard_uses_configured_policy():
    guard = GroundingGuard(
        GroundingPolicy(
            require_years=False,
        )
    )

    result = guard.assess(
        "¿Cuál es el calendario de 2027?",
        (chunk("Calendario institucional de 2026."),),
    )

    assert result.assessment.supported is True


@pytest.mark.parametrize(
    "values",
    [
        {"require_years": 1},
        {"require_locations": "yes"},
        {"require_services": None},
        {"require_identifiers": 0},
        {"require_regulation_scope": []},
    ],
)
def test_rejects_invalid_policy(values):
    with pytest.raises(ValueError):
        GroundingPolicy(**values)
