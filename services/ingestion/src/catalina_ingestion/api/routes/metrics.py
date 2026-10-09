from typing import Annotated

from fastapi import (
    APIRouter,
    Request,
    Security,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.exceptions import (
    InvalidAccessTokenError,
)
from catalina_ingestion.schemas.metrics import (
    IngestionMetricsResponse,
    RagMetricsResponse,
    SystemSummaryMetricsResponse,
)
from catalina_ingestion.services.auth import (
    AuthService,
)
from catalina_ingestion.services.metrics import (
    MetricsService,
)

router = APIRouter(
    tags=["metrics"],
)

bearer_scheme = HTTPBearer(
    auto_error=False,
)


def _get_auth_service(
    request: Request,
) -> AuthService:
    service = getattr(
        request.app.state,
        "auth_service",
        None,
    )

    if service is None:
        raise RuntimeError("AuthService no ha sido inicializado.")

    return service


def _get_metrics_service(
    request: Request,
) -> MetricsService:
    service = getattr(
        request.app.state,
        "metrics_service",
        None,
    )

    if service is None:
        raise RuntimeError("MetricsService no ha sido inicializado.")

    return service


async def _current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise InvalidAccessTokenError

    return await _get_auth_service(request).get_current_user(
        access_token=credentials.credentials,
    )


CurrentUser = Annotated[
    AuthenticatedUser,
    Security(_current_user),
]


@router.get(
    "/admin/metrics/summary",
    response_model=SystemSummaryMetricsResponse,
)
async def summary_metrics(
    request: Request,
    current_user: CurrentUser,
) -> SystemSummaryMetricsResponse:
    result = await _get_metrics_service(request).get_summary(
        current_user=current_user,
    )

    return SystemSummaryMetricsResponse(
        users_total=result.users_total,
        users_active=result.users_active,
        conversations_total=(result.conversations_total),
        messages_total=result.messages_total,
        documents_total=result.documents_total,
        documents_active=(result.documents_active),
        documents_inactive=(result.documents_inactive),
        versions_total=result.versions_total,
        versions_active=result.versions_active,
        versions_pending=(result.versions_pending),
        versions_failed=result.versions_failed,
    )


@router.get(
    "/admin/metrics/ingestion",
    response_model=IngestionMetricsResponse,
)
async def ingestion_metrics(
    request: Request,
    current_user: CurrentUser,
) -> IngestionMetricsResponse:
    result = await _get_metrics_service(request).get_ingestion_metrics(
        current_user=current_user,
    )

    return IngestionMetricsResponse(
        jobs_total=result.jobs_total,
        jobs_pending=result.jobs_pending,
        jobs_indexing=result.jobs_indexing,
        jobs_completed=result.jobs_completed,
        jobs_failed=result.jobs_failed,
        average_progress=result.average_progress,
        indexing_runs_total=(result.indexing_runs_total),
        indexing_runs_preparing=(result.indexing_runs_preparing),
        indexing_runs_indexing=(result.indexing_runs_indexing),
        indexing_runs_verifying=(result.indexing_runs_verifying),
        indexing_runs_active=(result.indexing_runs_active),
        indexing_runs_failed=(result.indexing_runs_failed),
    )


@router.get(
    "/admin/metrics/rag",
    response_model=RagMetricsResponse,
)
async def rag_metrics(
    request: Request,
    current_user: CurrentUser,
) -> RagMetricsResponse:
    result = await _get_metrics_service(request).get_rag_metrics(
        current_user=current_user,
    )

    return RagMetricsResponse(
        messages_total=result.messages_total,
        messages_with_model=(result.messages_with_model),
        messages_without_model=(result.messages_without_model),
        average_response_time_seconds=(result.average_response_time_seconds),
        metric_records=result.metric_records,
        tokens_input_total=(result.tokens_input_total),
        tokens_output_total=(result.tokens_output_total),
        average_satisfaction=(result.average_satisfaction),
        average_precision=(result.average_precision),
    )
