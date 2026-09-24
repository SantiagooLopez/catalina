from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)
from pydantic import BaseModel

from catalina_ingestion.services.health import (
    HealthService,
)

router = APIRouter(
    tags=["health"],
)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class DependencyStatusResponse(BaseModel):
    postgres: Literal["ok", "error"]
    qdrant: Literal["ok", "error"]
    ollama: Literal["ok", "error"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str
    dependencies: DependencyStatusResponse


def get_health_service() -> HealthService:
    return HealthService()


@router.get(
    "/health",
    response_model=HealthResponse,
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="catalina-ingestion",
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": ("Una o más dependencias no están disponibles."),
        }
    },
)
async def readiness(
    response: Response,
    service: Annotated[
        HealthService,
        Depends(get_health_service),
    ],
) -> ReadinessResponse:
    result = await service.check_readiness()

    if not result.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status=("ready" if result.ready else "not_ready"),
        service="catalina-ingestion",
        dependencies=DependencyStatusResponse(
            postgres=("ok" if result.postgres else "error"),
            qdrant=("ok" if result.qdrant else "error"),
            ollama=("ok" if result.ollama else "error"),
        ),
    )
