from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from catalina_ingestion.api.app import create_app


def guest_client():
    app = create_app()
    service = SimpleNamespace(answer=AsyncMock(return_value=SimpleNamespace(
        query="Hola", text="Hola, ¿cómo estás?", citations=(),
        generated=False, reason="conversational", model=None,
    )))
    app.state.answer_service = service
    return TestClient(app), service


def test_guest_can_ask_without_account_or_conversation():
    client, service = guest_client()
    response = client.post("/api/v1/guest/answers", json={"query": " Hola "})
    assert response.status_code == 200
    assert response.json() == {
        "query": "Hola", "text": "Hola, ¿cómo estás?", "citations": [],
        "generated": False, "reason": "conversational", "model": None,
    }
    assert service.answer.await_args.args[0].query == "Hola"
    assert service.answer.await_args.kwargs == {}


def test_guest_rejects_blank_and_oversized_questions():
    client, service = guest_client()
    for query in ("   ", "a" * 1001):
        assert client.post("/api/v1/guest/answers", json={"query": query}).status_code == 422
    service.answer.assert_not_awaited()


def test_guest_shares_answer_rate_limit():
    client, service = guest_client()
    middleware = next(
        m for m in client.app.user_middleware if m.cls.__name__ == "RateLimitMiddleware"
    )
    middleware.kwargs["answers_limit"] = 1
    assert client.post("/api/v1/guest/answers", json={"query": "Hola"}).status_code == 200
    limited = client.post("/api/v1/guest/answers", json={"query": "Hola"})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    service.answer.assert_awaited_once()
