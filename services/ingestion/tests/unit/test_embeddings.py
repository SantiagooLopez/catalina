import json

import httpx
import pytest

from catalina_ingestion.core.config import Settings
from catalina_ingestion.domain.exceptions import (
    EmbeddingError,
)
from catalina_ingestion.domain.processed import DocumentChunk
from catalina_ingestion.services.embeddings import (
    EmbeddingService,
)


def create_chunk(index: int, text: str) -> DocumentChunk:
    return DocumentChunk(
        index=index,
        text=text,
        section=None,
        page_start=1,
        page_end=1,
        source_block_indexes=(index,),
        character_count=len(text),
        estimated_tokens=5,
        text_sha256=f"{index:064d}",
    )


def create_settings(**overrides) -> Settings:
    values = {
        "database_password": "password-for-tests",
        "ollama_url": "http://ollama.test",
        "ollama_embedding_model": "embeddinggemma:latest",
        "embedding_dimension": 3,
        "embedding_batch_size": 2,
        "embedding_retry_attempts": 2,
        "embedding_retry_wait_seconds": 0,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_generates_embeddings_in_batches():
    request_count = 0

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        payload = json.loads(request.content)
        inputs = payload["input"]

        return httpx.Response(
            200,
            json={
                "model": "embeddinggemma:latest",
                "embeddings": [[0.1, 0.2, 0.3] for _ in inputs],
                "total_duration": 100,
                "load_duration": 10,
                "prompt_eval_count": len(inputs),
            },
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await EmbeddingService(
            settings=create_settings(),
            client=client,
        ).generate(
            [
                create_chunk(0, "Texto uno"),
                create_chunk(1, "Texto dos"),
                create_chunk(2, "Texto tres"),
            ]
        )

    assert request_count == 2
    assert len(result.chunks) == 3
    assert result.statistics.batch_count == 2
    assert result.statistics.input_count == 3


@pytest.mark.asyncio
async def test_rejects_wrong_dimension():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2]]},
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = EmbeddingService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(EmbeddingError) as captured:
            await service.generate([create_chunk(0, "Texto")])

    assert captured.value.code == "EMBEDDING_DIMENSION_MISMATCH"


@pytest.mark.asyncio
async def test_rejects_zero_vector():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"embeddings": [[0.0, 0.0, 0.0]]},
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = EmbeddingService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(EmbeddingError) as captured:
            await service.generate([create_chunk(0, "Texto")])

    assert captured.value.code == "ZERO_EMBEDDING"


@pytest.mark.asyncio
async def test_retries_temporary_error():
    request_count = 0

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            return httpx.Response(503)

        return httpx.Response(
            200,
            json={
                "embeddings": [[0.1, 0.2, 0.3]],
            },
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await EmbeddingService(
            settings=create_settings(),
            client=client,
        ).generate([create_chunk(0, "Texto")])

    assert request_count == 2
    assert len(result.chunks) == 1


@pytest.mark.asyncio
async def test_generates_embeddings_from_plain_texts():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(request.content)

        assert payload["input"] == ["¿Cuál es el reglamento estudiantil?"]
        assert payload["model"] == "embeddinggemma:latest"

        return httpx.Response(
            200,
            json={
                "model": "embeddinggemma:latest",
                "embeddings": [[0.1, 0.2, 0.3]],
                "total_duration": 100,
                "load_duration": 10,
                "prompt_eval_count": 7,
            },
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await EmbeddingService(
            settings=create_settings(),
            client=client,
        ).generate_texts(["¿Cuál es el reglamento estudiantil?"])

    assert result.model == "embeddinggemma:latest"
    assert result.dimension == 3
    assert result.vectors == ((0.1, 0.2, 0.3),)
    assert result.statistics.input_count == 1
    assert result.statistics.batch_count == 1


@pytest.mark.asyncio
async def test_rejects_empty_text_collection():
    service = EmbeddingService(
        settings=create_settings(),
    )

    with pytest.raises(EmbeddingError) as captured:
        await service.generate_texts([])

    assert captured.value.code == "NO_TEXTS_TO_EMBED"


@pytest.mark.asyncio
async def test_rejects_blank_text():
    service = EmbeddingService(
        settings=create_settings(),
    )

    with pytest.raises(EmbeddingError) as captured:
        await service.generate_texts(["   "])

    assert captured.value.code == "EMPTY_TEXT_TO_EMBED"
