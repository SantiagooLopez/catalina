import httpx

from catalina_ingestion.core.config import get_settings

_client: httpx.AsyncClient | None = None


async def open_ollama_client() -> httpx.AsyncClient:
    global _client

    if _client is not None:
        return _client

    settings = get_settings()

    client = httpx.AsyncClient(
        base_url=settings.ollama_url.rstrip("/"),
        timeout=httpx.Timeout(settings.ollama_timeout_seconds),
    )

    try:
        response = await client.get("/api/tags")
        response.raise_for_status()

        installed_models = {model["name"] for model in response.json().get("models", [])}

        required_models = {
            settings.ollama_embedding_model,
            settings.ollama_generation_model,
        }

        missing_models = sorted(required_models - installed_models)

        if missing_models:
            raise RuntimeError(
                "No están instalados los modelos requeridos de Ollama: " + ", ".join(missing_models)
            )

    except Exception:
        await client.aclose()
        raise

    _client = client
    return client


def get_ollama_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("El cliente de Ollama no ha sido inicializado")

    return _client


async def close_ollama_client() -> None:
    global _client

    if _client is not None:
        await _client.aclose()
        _client = None
