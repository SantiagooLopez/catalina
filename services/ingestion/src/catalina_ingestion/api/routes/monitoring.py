from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Query,
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
from catalina_ingestion.domain.monitoring import (
    IndexingRun,
    IngestionJob,
)
from catalina_ingestion.schemas.monitoring import (
    IndexingRunListResponse,
    IndexingRunResponse,
    IngestionJobListResponse,
    IngestionJobResponse,
)
from catalina_ingestion.services.auth import (
    AuthService,
)
from catalina_ingestion.services.monitoring import (
    MonitoringService,
)

router = APIRouter(
    tags=["monitoring"],
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


def _get_monitoring_service(
    request: Request,
) -> MonitoringService:
    service = getattr(
        request.app.state,
        "monitoring_service",
        None,
    )

    if service is None:
        raise RuntimeError("MonitoringService no ha sido inicializado.")

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


def _job_response(
    job: IngestionJob,
) -> IngestionJobResponse:
    return IngestionJobResponse(
        id=job.id,
        document_version_id=job.document_version_id,
        document_id=job.document_id,
        document_code=job.document_code,
        version=job.version,
        type=job.type,
        state=job.state,
        progress=job.progress,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        priority=job.priority,
        configuration=job.configuration,
        worker_id=job.worker_id,
        locked_until=job.locked_until,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        updated_at=job.updated_at,
        error_code=job.error_code,
        error_detail=job.error_detail,
    )


def _run_response(
    run: IndexingRun,
) -> IndexingRunResponse:
    return IndexingRunResponse(
        id=run.id,
        document_version_id=run.document_version_id,
        document_id=run.document_id,
        ingestion_job_id=run.ingestion_job_id,
        document_code=run.document_code,
        version=run.version,
        state=run.state,
        qdrant_collection=run.qdrant_collection,
        embedding_model=run.embedding_model,
        embedding_dimension=run.embedding_dimension,
        chunking_configuration=(run.chunking_configuration),
        expected_chunks=run.expected_chunks,
        indexed_chunks=run.indexed_chunks,
        attempt=run.attempt,
        created_at=run.created_at,
        activated_at=run.activated_at,
        finished_at=run.finished_at,
        updated_at=run.updated_at,
        error_code=run.error_code,
        error_detail=run.error_detail,
    )


@router.get(
    "/admin/ingestion-jobs",
    response_model=IngestionJobListResponse,
)
async def list_ingestion_jobs(
    request: Request,
    current_user: CurrentUser,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> IngestionJobListResponse:
    jobs = await _get_monitoring_service(request).list_ingestion_jobs(
        current_user=current_user,
        limit=limit,
        offset=offset,
    )

    return IngestionJobListResponse(
        items=[_job_response(job) for job in jobs],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/ingestion-jobs/{job_id}",
    response_model=IngestionJobResponse,
)
async def get_ingestion_job(
    job_id: UUID,
    request: Request,
    current_user: CurrentUser,
) -> IngestionJobResponse:
    job = await _get_monitoring_service(request).get_ingestion_job(
        current_user=current_user,
        job_id=job_id,
    )

    return _job_response(job)


@router.get(
    "/admin/documents/{document_id}/jobs",
    response_model=IngestionJobListResponse,
)
async def list_document_jobs(
    document_id: int,
    request: Request,
    current_user: CurrentUser,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> IngestionJobListResponse:
    jobs = await _get_monitoring_service(request).list_document_jobs(
        current_user=current_user,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )

    return IngestionJobListResponse(
        items=[_job_response(job) for job in jobs],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/indexing-runs",
    response_model=IndexingRunListResponse,
)
async def list_indexing_runs(
    request: Request,
    current_user: CurrentUser,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> IndexingRunListResponse:
    runs = await _get_monitoring_service(request).list_indexing_runs(
        current_user=current_user,
        limit=limit,
        offset=offset,
    )

    return IndexingRunListResponse(
        items=[_run_response(run) for run in runs],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/indexing-runs/{run_id}",
    response_model=IndexingRunResponse,
)
async def get_indexing_run(
    run_id: UUID,
    request: Request,
    current_user: CurrentUser,
) -> IndexingRunResponse:
    run = await _get_monitoring_service(request).get_indexing_run(
        current_user=current_user,
        run_id=run_id,
    )

    return _run_response(run)
