import json

import httpx
import pytest

from catalina_ingestion.core.config import Settings
from catalina_ingestion.domain.exceptions import EmbeddingError
from catalina_ingestion.services.embeddings import EmbeddingService
from catalina_ingestion.services.query_embedding import QueryEmbeddingService


def create_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_password="password-for-tests",
        ollama_url="http://ollama.test",
        ollama_embedding_model="embeddinggemma:latest",
        embedding_dimension=3,
        embedding_batch_size=2,
        embedding_retry_attempts=2,
        embedding_retry_wait_seconds=0,
        ollama_truncate=False,
    )


@pytest.mark.asyncio
async def test_generates_vector_for_normalized_query():
    original = "  ¿Do\u0301nde   está\nla biblioteca?  "
    expected = "¿Dónde está la biblioteca?"
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content)

        assert request.url.path == "/api/embed"
        assert payload["input"] == [expected]
        assert payload["model"] == "embeddinggemma:latest"
        assert payload["truncate"] is False

        return httpx.Response(
            200,
            json={
                "model": "embeddinggemma:latest",
                "embeddings": [[0.1, 0.2, 0.3]],
                "prompt_eval_count": 8,
            },
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = QueryEmbeddingService(
            embedding_service=EmbeddingService(
                settings=create_settings(),
                client=client,
            )
        )
        result = await service.generate(original)

    assert request_count == 1
    assert result.original_query == original
    assert result.normalized_query == expected
    assert result.vector == (0.1, 0.2, 0.3)
    assert result.dimension == 3
    assert result.model == "embeddinggemma:latest"
    assert result.statistics.input_count == 1
    assert result.statistics.prompt_eval_count == 8


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_code"),
    [
        ("", "EMPTY_QUERY"),
        (" \n\t ", "EMPTY_QUERY"),
        ("x" * 1001, "QUERY_TOO_LONG"),
        ("Biblioteca\x00", "INVALID_QUERY_CHARACTER"),
        (None, "INVALID_QUERY_TYPE"),
    ],
)
async def test_rejects_invalid_queries_before_http(query, expected_code):
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500)

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = QueryEmbeddingService(
            embedding_service=EmbeddingService(
                settings=create_settings(),
                client=client,
            )
        )

        with pytest.raises(EmbeddingError) as captured:
            await service.generate(query)

    assert captured.value.code == expected_code
    assert request_count == 0


@pytest.mark.asyncio
async def test_propagates_dimension_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2]]},
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = QueryEmbeddingService(
            embedding_service=EmbeddingService(
                settings=create_settings(),
                client=client,
            )
        )

        with pytest.raises(EmbeddingError) as captured:
            await service.generate("¿Dónde está la biblioteca?")

    assert captured.value.code == "EMBEDDING_DIMENSION_MISMATCH"


@pytest.mark.asyncio
async def test_rejects_enabled_truncation():
    settings = create_settings().model_copy(update={"ollama_truncate": True})
    service = QueryEmbeddingService(embedding_service=EmbeddingService(settings=settings))

    with pytest.raises(EmbeddingError) as captured:
        await service.generate("¿Dónde está la biblioteca?")

    assert captured.value.code == "QUERY_TRUNCATION_ENABLED"
