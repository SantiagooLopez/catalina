import asyncio
from dataclasses import dataclass

from catalina_ingestion.clients.ollama import (
    get_ollama_client,
)
from catalina_ingestion.clients.qdrant import (
    get_qdrant_client,
)
from catalina_ingestion.core.config import get_settings
from catalina_ingestion.db.postgres import (
    postgres_connection,
)


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    postgres: bool
    qdrant: bool
    ollama: bool

    @property
    def ready(self) -> bool:
        return self.postgres and self.qdrant and self.ollama


class HealthService:
    async def check_readiness(
        self,
    ) -> ReadinessResult:
        (
            postgres,
            qdrant,
            ollama,
        ) = await asyncio.gather(
            self._check_postgres(),
            self._check_qdrant(),
            self._check_ollama(),
        )

        return ReadinessResult(
            postgres=postgres,
            qdrant=qdrant,
            ollama=ollama,
        )

    async def _check_postgres(self) -> bool:
        try:
            async with postgres_connection() as connection:
                cursor = await connection.execute("SELECT 1")
                row = await cursor.fetchone()

            return row == (1,)

        except Exception:
            return False

    async def _check_qdrant(self) -> bool:
        try:
            settings = get_settings()
            client = get_qdrant_client()

            await client.get_collection(settings.qdrant_collection)

            return True

        except Exception:
            return False

    async def _check_ollama(self) -> bool:
        try:
            settings = get_settings()
            client = get_ollama_client()

            response = await client.get("/api/tags")
            response.raise_for_status()

            installed_models = {
                model["name"]
                for model in response.json().get(
                    "models",
                    [],
                )
            }

            required_models = {
                settings.ollama_embedding_model,
                settings.ollama_generation_model,
            }

            return required_models.issubset(installed_models)

        except Exception:
            return False
