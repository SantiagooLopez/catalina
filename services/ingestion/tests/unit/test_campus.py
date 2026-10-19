from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from catalina_ingestion.api.app import create_app
from catalina_ingestion.domain.generation import GenerationReason
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.campus import (
    campus_catalog,
    directory_answer,
    match_locations,
    public_catalog,
)
from catalina_ingestion.services.chat import ChatService


def test_catalog_marks_reference_pixels_and_unknown_positions_explicitly():
    data = public_catalog()
    assert data["reference_width"] == 760
    places = {place["id"]: place for place in data["locations"]}
    assert places["bienestar"]["anchor_id"] == "claustro"
    assert places["bienestar"]["reference_point"] is None
    assert places["bienestar"]["resolved_address"] == places["claustro"]["address"]
    assert places["tesoreria"]["anchor_id"] == "las-torres"
    assert places["tesoreria"]["resolved_address"] == places["las-torres"]["address"]
    assert "lat" not in places["claustro"]
    assert len({p.id for p in campus_catalog().locations}) == len(campus_catalog().locations)


def test_ambiguous_library_does_not_choose_a_branch_arbitrarily():
    matches = match_locations("¿Dónde queda la biblioteca?")
    assert {place.id for place in matches} == {"biblioteca-central", "biblioteca-sede-4"}
    specific = match_locations("¿Dónde queda la biblioteca de la sede 4?")
    assert [place.id for place in specific] == ["biblioteca-sede-4"]


def test_psychological_services_are_not_confused_with_faculty():
    assert [place.id for place in match_locations("Unidad de Servicios Psicológicos")] == [
        "servicios-psicologicos",
    ]
    assert [place.id for place in match_locations("Facultad de Psicología")] == ["psicologia"]


def test_only_location_requests_use_directory_in_regular_chat():
    assert directory_answer("Estoy estudiando psicología") is None
    assert directory_answer("¿Qué servicios ofrece Bienestar?") is None
    answer = directory_answer("¿Dónde queda Bienestar?")
    assert answer.reason is GenerationReason.CAMPUS_LOCATION
    assert answer.locations == ("bienestar",)
    assert "El Claustro" in answer.text and "oficina" in answer.text
    assert not answer.generated


def test_confirmed_treasury_uses_torres_but_keeps_office_pending():
    answer = directory_answer("¿Dónde queda Tesorería?")
    assert answer.locations == ("tesoreria",)
    assert "Las Torres" in answer.text
    assert "confirmar" in answer.text


def test_unknown_campus_place_is_pending_but_other_locations_keep_normal_routing():
    answer = directory_answer("¿Dónde queda la cafetería de la universidad?")
    assert answer.reason is GenerationReason.CAMPUS_LOCATION
    assert answer.locations == ()
    assert directory_answer("¿Dónde queda Marte?") is None
    assert directory_answer("¿Cómo puedo llegar a Bienestar?").locations == ("bienestar",)


def test_map_question_uses_selected_campus_and_does_not_invent_hours():
    answer = directory_answer("¿Qué dependencias hay aquí?", selected_id="claustro", force=True)
    assert "Bienestar" in answer.text
    assert "bienestar" in answer.locations
    hours = directory_answer("¿A qué hora abren?", selected_id="lenguas", force=True)
    assert "no tiene ese dato verificado" in hours.text
    assert directory_answer("¿Cuál es la dirección?", selected_id="psicologia", force=True)


@pytest.mark.asyncio
async def test_location_response_needs_neither_generation_nor_qdrant():
    generation = SimpleNamespace(chat=AsyncMock())
    rag = SimpleNamespace(answer=AsyncMock())
    chat = ChatService(generation_service=generation, rag_service=rag)
    answer = await chat.answer(RetrievalQuery(query="¿Dónde queda el Instituto de Lenguas?"))
    assert answer.locations == ("lenguas",)
    generation.chat.assert_not_awaited()
    rag.answer.assert_not_awaited()


def test_public_campus_api_validation_and_context():
    client = TestClient(create_app())
    assert client.get("/api/v1/campus/locations").status_code == 200
    response = client.post("/api/v1/campus/query", json={
        "query": "¿Dónde queda la Facultad de Psicología?", "selected_id": None,
    })
    assert response.status_code == 200
    assert response.json()["locations"] == ["psicologia"]
    assert "46" in response.json()["text"]
    assert client.post("/api/v1/campus/query", json={"query": "   "}).status_code == 422
    assert client.post("/api/v1/campus/query", json={
        "query": "¿Dónde queda?", "selected_id": "missing-place",
    }).status_code == 404


def test_guest_location_answer_includes_map_identifiers_without_authentication():
    app = create_app()
    app.state.answer_service = ChatService()
    client = TestClient(app)
    response = client.post("/api/v1/guest/answers", json={
        "query": "¿Dónde queda la Facultad de Psicología?",
    })
    assert response.status_code == 200
    assert response.json()["locations"] == ["psicologia"]
    assert response.json()["reason"] == "campus_location"
    assert not response.json()["generated"]


def test_user_confirmed_buildings_have_independent_positions():
    places = {p.id: p for p in campus_catalog().locations}
    for key in ("sede-4", "biblioteca-sede-4", "carrera-13", "las-torres", "derecho"):
        assert places[key].reference_point is not None
        assert places[key].source_id == "confirmed"
    assert places["derecho"].parent_id == "las-torres"
    assert places["derecho"].address is None
    assert "construcción" in places["carrera-13"].note
    assert places["biblioteca-sede-4"].reference_point != places["sede-4"].reference_point


def test_colored_campus_blocks_and_hierarchical_numbers_match_confirmed_plan():
    places = {p.id: p for p in campus_catalog().locations}
    assert len(places["liceo-referencia"].reference_areas) == 2
    assert places["claustro"].map_label == "5"
    assert places["capilla"].parent_id == "claustro"
    assert places["capilla"].map_label == "5.2"
    assert places["auditorio-sede-4"].parent_id == "sede-4"
    assert places["auditorio-sede-4"].map_label == "1.2"
    assert places["polideportivo"].parent_id == "las-torres"
    assert places["polideportivo"].map_label == "3.3"
    assert places["polideportivo"].reference_areas
    answer = directory_answer("¿Dónde quedan las canchas de fútbol?")
    assert answer.locations == ("polideportivo",)
    assert "Las Torres" in answer.text


def test_confirmed_shared_locations_resolve_nested_faculty_and_campus():
    places = {p["id"]: p for p in public_catalog()["locations"]}
    assert "extension" not in places
    for key in ("liceo-primaria", "liceo-bachillerato"):
        assert places[key]["anchor_id"] == "liceo-referencia"
    for key in ("registro-academico", "admisiones", "tesoreria"):
        assert places[key]["anchor_id"] == "las-torres"
    assert places["consultorio-juridico"]["parent_id"] == "derecho"
    assert places["consultorio-juridico"]["anchor_id"] == "derecho"
    assert places["consultorio-juridico"]["resolved_address"] == places["las-torres"]["address"]
    answer = directory_answer("¿Dónde queda el consultorio jurídico?")
    assert "Las Torres" in answer.text
    assert places["las-torres"]["address"] in answer.text
