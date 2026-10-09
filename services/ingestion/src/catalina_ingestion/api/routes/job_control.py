from typing import Annotated
from uuid import UUID

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
from catalina_ingestion.schemas.job_control import (
    JobActionResponse,
    ReindexRequest,
)
from catalina_ingestion.services.auth import (
    AuthService,
)
from catalina_ingestion.services.job_control import (
    JobControlService,
)

router = APIRouter(
    tags=["job-control"],
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


def _get_job_control_service(
    request: Request,
) -> JobControlService:
    service = getattr(
        request.app.state,
        "job_control_service",
        None,
    )

    if service is None:
        raise RuntimeError("JobControlService no ha sido inicializado.")

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


@router.post(
    "/admin/ingestion-jobs/{job_id}/retry",
    response_model=JobActionResponse,
)
async def retry_ingestion_job(
    job_id: UUID,
    request: Request,
    current_user: CurrentUser,
) -> JobActionResponse:
    result = await _get_job_control_service(request).retry_job(
        current_user=current_user,
        job_id=job_id,
    )

    return JobActionResponse(
        job_id=result.job_id,
        document_id=result.document_id,
        document_version_id=(result.document_version_id),
        type=result.type,
        state=result.state,
    )


@router.post(
    ("/admin/documents/{document_id}/versions/{version_id}/reindex"),
    response_model=JobActionResponse,
    status_code=201,
)
async def request_reindex(
    document_id: int,
    version_id: int,
    payload: ReindexRequest,
    request: Request,
    current_user: CurrentUser,
) -> JobActionResponse:
    result = await _get_job_control_service(request).request_reindex(
        current_user=current_user,
        document_id=document_id,
        version_id=version_id,
        reason=payload.reason,
    )

    return JobActionResponse(
        job_id=result.job_id,
        document_id=result.document_id,
        document_version_id=(result.document_version_id),
        type=result.type,
        state=result.state,
    )
