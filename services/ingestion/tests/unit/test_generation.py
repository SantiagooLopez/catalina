import json

import httpx
import pytest

from catalina_ingestion.core.config import Settings
from catalina_ingestion.domain.exceptions import GenerationError
from catalina_ingestion.domain.generation import GenerationPrompt
from catalina_ingestion.domain.rag_context import ContextSource
from catalina_ingestion.services.generation import GenerationService


def create_settings(**overrides) -> Settings:
    values = {
        "database_password": "password-for-tests",
        "ollama_url": "http://ollama.test",
        "ollama_generation_model": "llama3.2:3b",
        "ollama_keep_alive": "10m",
        "generation_temperature": 0.0,
        "generation_max_tokens": 64,
        "generation_retry_attempts": 2,
        "generation_retry_wait_seconds": 0,
    }
    values.update(overrides)
    return Settings(**values)


def create_source() -> ContextSource:
    return ContextSource(
        citation_id="S1",
        point_id="point-1",
        document_id=1,
        document_version_id=1,
        document_name="Reglamento del Estudiante",
        version="406-2026",
        page_start=12,
        page_end=12,
        section="Artículo 20",
        index_run_id="run-1",
    )


def create_prompt() -> GenerationPrompt:
    return GenerationPrompt(
        system_message="Usa solamente la evidencia.",
        user_message=(
            "Pregunta: ¿Cuál es el procedimiento?\nEvidencia: [S1] Procedimiento institucional."
        ),
        allowed_citations=("S1",),
    )


def success_payload(**overrides):
    payload = {
        "model": "llama3.2:3b",
        "message": {
            "role": "assistant",
            "content": ("Debe seguirse el procedimiento institucional. [S1]"),
        },
        "done": True,
        "total_duration": 1000,
        "load_duration": 100,
        "prompt_eval_count": 50,
        "prompt_eval_duration": 200,
        "eval_count": 20,
        "eval_duration": 300,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_generates_answer_with_expected_payload():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == "/api/chat"

        payload = json.loads(request.content)

        assert payload["model"] == "llama3.2:3b"
        assert payload["stream"] is False
        assert payload["keep_alive"] == "10m"
        assert payload["options"]["temperature"] == 0.0
        assert payload["options"]["num_predict"] == 64

        assert payload["messages"] == [
            {
                "role": "system",
                "content": "Usa solamente la evidencia.",
            },
            {
                "role": "user",
                "content": (
                    "Pregunta: ¿Cuál es el procedimiento?\n"
                    "Evidencia: [S1] Procedimiento institucional."
                ),
            },
        ]

        return httpx.Response(
            200,
            json=success_payload(),
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await GenerationService(
            settings=create_settings(),
            client=client,
        ).generate(
            query="¿Cuál es el procedimiento?",
            prompt=create_prompt(),
            citations=(create_source(),),
        )

    assert result.generated is True
    assert result.model == "llama3.2:3b"
    assert result.citations[0].citation_id == "S1"
    assert "[S1]" in result.text
    assert result.statistics is not None
    assert result.statistics.total_duration_ns == 1000
    assert result.statistics.prompt_eval_count == 50
    assert result.statistics.eval_count == 20


@pytest.mark.asyncio
async def test_retries_temporary_server_error():
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
            json=success_payload(),
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await GenerationService(
            settings=create_settings(),
            client=client,
        ).generate(
            query="Pregunta",
            prompt=create_prompt(),
            citations=(create_source(),),
        )

    assert request_count == 2
    assert result.generated is True


@pytest.mark.asyncio
async def test_does_not_retry_permanent_client_error():
    request_count = 0

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(400)

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = GenerationService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(GenerationError) as captured:
            await service.generate(
                query="Pregunta",
                prompt=create_prompt(),
                citations=(create_source(),),
            )

    assert request_count == 1
    assert captured.value.code == "OLLAMA_GENERATION_REJECTED"


@pytest.mark.asyncio
async def test_rejects_invalid_json_response():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"esto no es json",
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = GenerationService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(GenerationError) as captured:
            await service.generate(
                query="Pregunta",
                prompt=create_prompt(),
                citations=(create_source(),),
            )

    assert captured.value.code == "INVALID_OLLAMA_GENERATION_RESPONSE"


@pytest.mark.asyncio
async def test_rejects_unexpected_model():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=success_payload(model="otro-modelo"),
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = GenerationService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(GenerationError) as captured:
            await service.generate(
                query="Pregunta",
                prompt=create_prompt(),
                citations=(create_source(),),
            )

    assert captured.value.code == "UNEXPECTED_GENERATION_MODEL"


@pytest.mark.asyncio
async def test_rejects_incomplete_generation():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=success_payload(done=False),
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = GenerationService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(GenerationError) as captured:
            await service.generate(
                query="Pregunta",
                prompt=create_prompt(),
                citations=(create_source(),),
            )

    assert captured.value.code == "INCOMPLETE_GENERATION"


@pytest.mark.asyncio
async def test_rejects_empty_generated_content():
    payload = success_payload()
    payload["message"]["content"] = "   "

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = GenerationService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(GenerationError) as captured:
            await service.generate(
                query="Pregunta",
                prompt=create_prompt(),
                citations=(create_source(),),
            )

    assert captured.value.code == "EMPTY_GENERATION_RESPONSE"


@pytest.mark.asyncio
async def test_rejects_citation_mismatch_before_http_call():
    service = GenerationService(
        settings=create_settings(),
    )

    with pytest.raises(GenerationError) as captured:
        await service.generate(
            query="Pregunta",
            prompt=create_prompt(),
            citations=(),
        )

    assert captured.value.code == "GENERATION_CITATION_MISMATCH"


@pytest.mark.asyncio
async def test_rejects_invalid_generation_metric():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=success_payload(eval_count=-1),
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = GenerationService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(GenerationError) as captured:
            await service.generate(
                query="Pregunta",
                prompt=create_prompt(),
                citations=(create_source(),),
            )

    assert captured.value.code == "INVALID_GENERATION_METRIC"


@pytest.mark.asyncio
async def test_normalizes_parenthesized_citation():
    payload = success_payload()
    payload["message"]["content"] = "Debe seguirse el procedimiento institucional. (S1)"

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await GenerationService(
            settings=create_settings(),
            client=client,
        ).generate(
            query="Pregunta",
            prompt=create_prompt(),
            citations=(create_source(),),
        )

    assert "[S1]" in result.text
    assert "(S1)" not in result.text


@pytest.mark.asyncio
async def test_rejects_missing_generation_citation():
    payload = success_payload()
    payload["message"]["content"] = "Respuesta institucional sin cita."

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = GenerationService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(GenerationError) as captured:
            await service.generate(
                query="Pregunta",
                prompt=create_prompt(),
                citations=(create_source(),),
            )

    assert captured.value.code == "MISSING_GENERATION_CITATION"


@pytest.mark.asyncio
async def test_rejects_unknown_generation_citation():
    payload = success_payload()
    payload["message"]["content"] = "Respuesta institucional. [S99]"

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
        )

    async with httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        service = GenerationService(
            settings=create_settings(),
            client=client,
        )

        with pytest.raises(GenerationError) as captured:
            await service.generate(
                query="Pregunta",
                prompt=create_prompt(),
                citations=(create_source(),),
            )

    assert captured.value.code == "UNKNOWN_GENERATION_CITATION"
