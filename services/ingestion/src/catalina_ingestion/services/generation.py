import json
import logging
import re
from collections.abc import Sequence
from time import perf_counter
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from catalina_ingestion.clients.ollama import get_ollama_client
from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.domain.exceptions import (
    GenerationError,
    TransientGenerationError,
)
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationPrompt,
    GenerationReason,
    GenerationStatistics,
)
from catalina_ingestion.domain.rag_context import ContextSource


class GenerationService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client

    async def generate(
        self,
        *,
        query: str,
        prompt: GenerationPrompt,
        citations: Sequence[ContextSource],
    ) -> GeneratedAnswer:
        if not query.strip():
            raise GenerationError(
                "EMPTY_GENERATION_QUERY",
                "La consulta de generación no puede estar vacía.",
            )

        citation_tuple = tuple(citations)

        expected_citations = tuple(source.citation_id for source in citation_tuple)

        if expected_citations != prompt.allowed_citations:
            raise GenerationError(
                "GENERATION_CITATION_MISMATCH",
                ("Las fuentes proporcionadas no coinciden con las citas permitidas del prompt."),
                {
                    "expected": list(prompt.allowed_citations),
                    "received": list(expected_citations),
                },
            )

        client = self.client or get_ollama_client()

        text, statistics = await self._request_with_retry(
            client=client,
            prompt=prompt,
        )

        text = self._normalize_citations(text)

        try:
            self._validate_citations(
                text=text,
                allowed_citations=prompt.allowed_citations,
            )
        except GenerationError as error:
            if error.code != "MISSING_GENERATION_CITATION":
                raise

            correction_prompt = self._build_citation_correction_prompt(
                prompt=prompt,
                previous_answer=text,
            )

            text, statistics = await self._request_with_retry(
                client=client,
                prompt=correction_prompt,
            )

            text = self._normalize_citations(text)

            self._validate_citations(
                text=text,
                allowed_citations=prompt.allowed_citations,
            )

        return GeneratedAnswer(
            query=query,
            text=text,
            generated=True,
            reason=GenerationReason.GENERATED,
            model=self.settings.ollama_generation_model,
            citations=citation_tuple,
            statistics=statistics,
        )

    @staticmethod
    def _build_citation_correction_prompt(
        *,
        prompt: GenerationPrompt,
        previous_answer: str,
    ) -> GenerationPrompt:
        allowed = ", ".join(f"[{citation}]" for citation in prompt.allowed_citations)

        user_message = (
            f"{prompt.user_message}\n\n"
            "RESPUESTA ANTERIOR SIN CITA VÁLIDA:\n"
            f"{previous_answer}\n\n"
            "CORRECCIÓN OBLIGATORIA:\n"
            "Reescribe la respuesta manteniendo únicamente "
            "afirmaciones respaldadas por la evidencia proporcionada. "
            "La respuesta debe contener al menos una de las citas "
            "permitidas y debe escribirla exactamente con corchetes. "
            f"Citas permitidas: {allowed}. "
            "No inventes identificadores ni utilices citas diferentes."
        )

        return GenerationPrompt(
            system_message=prompt.system_message,
            user_message=user_message,
            allowed_citations=prompt.allowed_citations,
        )

    async def _request_with_retry(
        self,
        *,
        client: httpx.AsyncClient,
        prompt: GenerationPrompt,
    ) -> tuple[str, GenerationStatistics]:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self.settings.generation_retry_attempts),
            wait=wait_exponential(
                multiplier=(self.settings.generation_retry_wait_seconds),
                min=self.settings.generation_retry_wait_seconds,
                max=8,
            ),
            retry=retry_if_exception_type(TransientGenerationError),
            reraise=True,
        )

        async for attempt in retrying:
            with attempt:
                return await self._request(
                    client=client,
                    prompt=prompt,
                )

        raise RuntimeError("El ciclo de reintentos terminó sin resultado.")

    async def _request(
        self,
        *,
        client: httpx.AsyncClient,
        prompt: GenerationPrompt,
    ) -> tuple[str, GenerationStatistics]:
        text, statistics = await self.chat(
            messages=[
                {"role": "system", "content": prompt.system_message},
                {"role": "user", "content": prompt.user_message},
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "minLength": 1, "maxLength": 700},
                    "citations": {
                        "type": "array", "minItems": 1, "maxItems": 4,
                        "items": {"type": "string", "enum": list(prompt.allowed_citations)},
                    },
                },
                "required": ["text", "citations"], "additionalProperties": False,
            },
            max_tokens=min(self.settings.generation_max_tokens, 384),
        )
        # Accept legacy plain text only through the existing strict citation validator.
        if not text.lstrip().startswith("{"):
            return text, statistics
        try:
            result = json.loads(text)
            answer_text = result["text"]
            citations = result["citations"]
            if not isinstance(answer_text, str) or not answer_text.strip():
                raise ValueError("Texto de respuesta vacío.")
            if not isinstance(citations, list) or not all(isinstance(c, str) for c in citations):
                raise ValueError("Lista de citas inválida.")
        except (ValueError, TypeError, KeyError) as error:
            raise GenerationError(
                "INVALID_OLLAMA_GENERATION_RESPONSE", "La respuesta estructurada no es válida.",
            ) from error
        unknown = [c for c in citations if c not in prompt.allowed_citations]
        if unknown:
            raise GenerationError(
                "UNKNOWN_GENERATION_CITATION", "La respuesta contiene citas no autorizadas.",
                {"unknown": unknown, "allowed": list(prompt.allowed_citations)},
            )
        # Render citations selected by the model, never infer or invent a missing source.
        missing = [f"[{c}]" for c in dict.fromkeys(citations) if f"[{c}]" not in answer_text]
        if missing:
            answer_text = answer_text.rstrip() + " " + " ".join(missing)
        return answer_text, statistics

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        output_schema: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, GenerationStatistics]:
        """Use the same validated Ollama transport for routing and ordinary chat."""
        started = perf_counter()
        client = self.client or get_ollama_client()
        payload: dict[str, Any] = {
            "model": self.settings.ollama_generation_model,
            "stream": False,
            "keep_alive": self.settings.ollama_keep_alive,
            "options": {
                "temperature": self.settings.generation_temperature,
                "num_predict": max_tokens or self.settings.generation_max_tokens,
            },
            "messages": messages,
        }
        if output_schema is not None:
            payload["format"] = output_schema
        try:
            response = await client.post(
                "/api/chat",
                json=payload,
            )
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
        ) as error:
            raise TransientGenerationError(
                "OLLAMA_GENERATION_CONNECTION_ERROR",
                "No fue posible comunicarse con Ollama.",
                {
                    "error_type": type(error).__name__,
                },
            ) from error

        if response.status_code == 429 or response.status_code >= 500:
            raise TransientGenerationError(
                "OLLAMA_GENERATION_TEMPORARY_ERROR",
                "Ollama presentó un error temporal de generación.",
                {
                    "status_code": response.status_code,
                },
            )

        if response.status_code >= 400:
            raise GenerationError(
                "OLLAMA_GENERATION_REJECTED",
                "Ollama rechazó la solicitud de generación.",
                {
                    "status_code": response.status_code,
                },
            )

        try:
            response_payload = response.json()
        except ValueError as error:
            raise GenerationError(
                "INVALID_OLLAMA_GENERATION_RESPONSE",
                "Ollama devolvió una respuesta JSON inválida.",
            ) from error

        if not isinstance(response_payload, dict):
            raise GenerationError(
                "INVALID_OLLAMA_GENERATION_RESPONSE",
                "Ollama devolvió una respuesta inválida.",
            )
        text, statistics = self._parse_response(response_payload)
        logging.getLogger("uvicorn.error").info(
            "ollama_timing total_ms=%.1f load_ms=%.1f prompt_tokens=%d prompt_ms=%.1f "
            "output_tokens=%d output_ms=%.1f",
            (perf_counter() - started) * 1000, statistics.load_duration_ns / 1e6,
            statistics.prompt_eval_count, statistics.prompt_eval_duration_ns / 1e6,
            statistics.eval_count, statistics.eval_duration_ns / 1e6,
        )
        return text, statistics

    def _parse_response(
        self,
        payload: dict[str, Any],
    ) -> tuple[str, GenerationStatistics]:
        returned_model = payload.get("model")

        if returned_model != self.settings.ollama_generation_model:
            raise GenerationError(
                "UNEXPECTED_GENERATION_MODEL",
                "Ollama respondió con un modelo inesperado.",
                {
                    "expected": (self.settings.ollama_generation_model),
                    "received": returned_model,
                },
            )

        if payload.get("done") is not True:
            raise GenerationError(
                "INCOMPLETE_GENERATION",
                "Ollama no marcó la generación como completada.",
            )

        message = payload.get("message")

        if not isinstance(message, dict):
            raise GenerationError(
                "MISSING_GENERATION_MESSAGE",
                "La respuesta de Ollama no contiene un mensaje.",
            )

        if message.get("role") != "assistant":
            raise GenerationError(
                "INVALID_GENERATION_ROLE",
                "Ollama devolvió un rol de mensaje inesperado.",
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise GenerationError(
                "EMPTY_GENERATION_RESPONSE",
                "Ollama devolvió una respuesta vacía.",
            )

        statistics = GenerationStatistics(
            total_duration_ns=self._metric(
                payload,
                "total_duration",
            ),
            load_duration_ns=self._metric(
                payload,
                "load_duration",
            ),
            prompt_eval_count=self._metric(
                payload,
                "prompt_eval_count",
            ),
            prompt_eval_duration_ns=self._metric(
                payload,
                "prompt_eval_duration",
            ),
            eval_count=self._metric(
                payload,
                "eval_count",
            ),
            eval_duration_ns=self._metric(
                payload,
                "eval_duration",
            ),
        )

        return content.strip(), statistics

    @staticmethod
    def _normalize_citations(
        text: str,
    ) -> str:
        return re.sub(
            r"\(\s*(S\d+)\s*\)",
            r"[\1]",
            text,
        )

    @staticmethod
    def _validate_citations(
        *,
        text: str,
        allowed_citations: tuple[str, ...],
    ) -> None:
        citations = set(
            re.findall(
                r"\[(S\d+)\]",
                text,
            )
        )

        if not citations:
            raise GenerationError(
                "MISSING_GENERATION_CITATION",
                ("La respuesta generada no contiene ninguna cita válida."),
            )

        allowed = set(allowed_citations)

        unknown = sorted(citations - allowed)

        if unknown:
            raise GenerationError(
                "UNKNOWN_GENERATION_CITATION",
                ("La respuesta generada contiene citas no autorizadas."),
                {
                    "unknown": unknown,
                    "allowed": sorted(allowed),
                },
            )

    @staticmethod
    def _metric(
        payload: dict[str, Any],
        name: str,
    ) -> int:
        value = payload.get(name, 0)

        if type(value) is not int or value < 0:
            raise GenerationError(
                "INVALID_GENERATION_METRIC",
                f"Ollama devolvió una métrica inválida: {name}.",
                {
                    "metric": name,
                    "value": value,
                },
            )

        return value
