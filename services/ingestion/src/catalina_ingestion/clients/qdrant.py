from qdrant_client import AsyncQdrantClient

from catalina_ingestion.core.config import get_settings

_client: AsyncQdrantClient | None = None


async def open_qdrant_client() -> AsyncQdrantClient:
    global _client

    if _client is not None:
        return _client

    settings = get_settings()

    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        timeout=settings.qdrant_timeout_seconds,
    )

    try:
        await client.get_collection(settings.qdrant_collection)
    except Exception:
        await client.close()
        raise

    _client = client
    return client


def get_qdrant_client() -> AsyncQdrantClient:
    if _client is None:
        raise RuntimeError("El cliente de Qdrant no ha sido inicializado")

    return _client


async def close_qdrant_client() -> None:
    global _client

    if _client is not None:
        await _client.close()
        _client = None
