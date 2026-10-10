from fastapi import FastAPI
from fastapi.testclient import TestClient

from catalina_ingestion.api.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)


def create_rate_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        RateLimitMiddleware,
        window_seconds=60,
        login_limit=2,
        answers_limit=2,
        uploads_limit=2,
    )

    @app.post("/api/v1/auth/login")
    async def login():
        return {"ok": True}

    @app.post("/api/v1/answers")
    async def answers():
        return {"ok": True}

    @app.post("/api/v1/admin/documents")
    async def documents():
        return {"ok": True}

    return app


def test_login_rate_limit():
    client = TestClient(create_rate_app())

    assert client.post("/api/v1/auth/login").status_code == 200

    assert client.post("/api/v1/auth/login").status_code == 200

    response = client.post("/api/v1/auth/login")

    assert response.status_code == 429

    payload = response.json()

    assert payload["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    assert payload["error"]["retryable"] is True

    assert response.headers.get("retry-after") is not None


def test_answers_rate_limit():
    client = TestClient(create_rate_app())

    assert client.post("/api/v1/answers").status_code == 200

    assert client.post("/api/v1/answers").status_code == 200

    assert client.post("/api/v1/answers").status_code == 429


def test_upload_rate_limit():
    client = TestClient(create_rate_app())

    assert client.post("/api/v1/admin/documents").status_code == 200

    assert client.post("/api/v1/admin/documents").status_code == 200

    assert client.post("/api/v1/admin/documents").status_code == 429


def test_security_headers_include_permissions_policy():
    app = FastAPI()

    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def test():
        return {"ok": True}

    response = TestClient(app).get("/test")

    assert response.status_code == 200

    assert response.headers["x-content-type-options"] == "nosniff"

    assert response.headers["x-frame-options"] == "DENY"

    assert response.headers["permissions-policy"] == ("camera=(), microphone=(), geolocation=()")
