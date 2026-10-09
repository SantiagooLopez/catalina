import json
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    File,
    Form,
    Request,
    Security,
    UploadFile,
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
from catalina_ingestion.repositories.documents import (
    DocumentDetail,
    DocumentVersionDetail,
)
from catalina_ingestion.schemas.documents import (
    DocumentListResponse,
    DocumentRegistrationRequest,
    DocumentRegistrationResponse,
    DocumentResponse,
    DocumentStatusRequest,
    DocumentVersionListResponse,
    DocumentVersionResponse,
)
from catalina_ingestion.services.auth import (
    AuthService,
)
from catalina_ingestion.services.document_admin import (
    DocumentAdminService,
)

router = APIRouter(
    tags=["documents"],
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


def _get_document_service(
    request: Request,
) -> DocumentAdminService:
    service = getattr(
        request.app.state,
        "document_admin_service",
        None,
    )

    if service is None:
        raise RuntimeError("DocumentAdminService no ha sido inicializado.")

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


def _document_response(
    document: DocumentDetail,
) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        nombre=document.nombre,
        tipo_archivo=document.tipo_archivo,
        categoria=document.categoria,
        descripcion=document.descripcion,
        estado=document.estado,
        fecha_carga=document.fecha_carga,
        codigo=document.codigo,
        idioma=document.idioma,
        origen=document.origen,
        metadatos=document.metadatos,
        fecha_actualizacion=(document.fecha_actualizacion),
    )


def _version_response(
    version: DocumentVersionDetail,
) -> DocumentVersionResponse:
    return DocumentVersionResponse(
        id=version.id,
        documento_id=version.documento_id,
        version=version.version,
        nombre_archivo_original=(version.nombre_archivo_original),
        extension=version.extension,
        mime_type=version.mime_type,
        tamano_bytes=version.tamano_bytes,
        hash_contenido=version.hash_contenido,
        estado=version.estado,
        total_paginas=version.total_paginas,
        total_secciones=version.total_secciones,
        total_chunks=version.total_chunks,
        modelo_embedding=version.modelo_embedding,
        dimension_embedding=(version.dimension_embedding),
        fecha_indexacion=version.fecha_indexacion,
        fecha_actualizacion=(version.fecha_actualizacion),
        error_codigo=version.error_codigo,
        error_detalle=version.error_detalle,
    )


def _parse_metadata(
    value: str,
) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("metadatos debe contener JSON válido.") from error

    if not isinstance(parsed, dict):
        raise ValueError("metadatos debe ser un objeto JSON.")

    return parsed


@router.post(
    "/admin/documents",
    response_model=DocumentRegistrationResponse,
    status_code=201,
)
async def register_document(
    request: Request,
    current_user: CurrentUser,
    file: Annotated[
        UploadFile,
        File(...),
    ],
    codigo: Annotated[str, Form()],
    nombre: Annotated[str, Form()],
    categoria: Annotated[str, Form()],
    version: Annotated[str, Form()],
    descripcion: Annotated[
        str | None,
        Form(),
    ] = None,
    idioma: Annotated[
        str,
        Form(),
    ] = "es",
    origen: Annotated[
        str | None,
        Form(),
    ] = None,
    metadatos: Annotated[
        str,
        Form(),
    ] = "{}",
) -> DocumentRegistrationResponse:
    payload = DocumentRegistrationRequest(
        codigo=codigo,
        nombre=nombre,
        categoria=categoria,
        version=version,
        descripcion=descripcion,
        idioma=idioma,
        origen=origen,
        metadatos=_parse_metadata(metadatos),
    )

    result = await _get_document_service(request).register_document(
        current_user=current_user,
        upload=file,
        request=payload,
    )

    return DocumentRegistrationResponse(
        document_id=result.document_id,
        document_version_id=(result.document_version_id),
        ingestion_job_id=(result.ingestion_job_id),
        codigo=result.codigo,
        version=result.version,
        estado=result.estado,
        sha256=result.sha256,
    )


@router.get(
    "/admin/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    request: Request,
    current_user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
) -> DocumentListResponse:
    documents = await _get_document_service(request).list_documents(
        current_user=current_user,
        limit=limit,
        offset=offset,
    )

    return DocumentListResponse(
        items=[_document_response(document) for document in documents],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/documents/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    document_id: int,
    request: Request,
    current_user: CurrentUser,
) -> DocumentResponse:
    document = await _get_document_service(request).get_document(
        current_user=current_user,
        document_id=document_id,
    )

    return _document_response(document)


@router.get(
    "/admin/documents/{document_id}/versions",
    response_model=DocumentVersionListResponse,
)
async def list_versions(
    document_id: int,
    request: Request,
    current_user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
) -> DocumentVersionListResponse:
    versions = await _get_document_service(request).list_versions(
        current_user=current_user,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )

    return DocumentVersionListResponse(
        items=[_version_response(version) for version in versions],
        limit=limit,
        offset=offset,
    )


@router.post(
    "/admin/documents/{document_id}/versions",
    response_model=DocumentRegistrationResponse,
    status_code=201,
)
async def register_version(
    document_id: int,
    request: Request,
    current_user: CurrentUser,
    file: Annotated[
        UploadFile,
        File(...),
    ],
    version: Annotated[
        str,
        Form(),
    ],
) -> DocumentRegistrationResponse:
    result = await _get_document_service(request).register_version(
        current_user=current_user,
        document_id=document_id,
        upload=file,
        version=version,
    )

    return DocumentRegistrationResponse(
        document_id=result.document_id,
        document_version_id=(result.document_version_id),
        ingestion_job_id=(result.ingestion_job_id),
        codigo=result.codigo,
        version=result.version,
        estado=result.estado,
        sha256=result.sha256,
    )


@router.patch(
    "/admin/documents/{document_id}/status",
    response_model=DocumentResponse,
)
async def update_document_status(
    document_id: int,
    payload: DocumentStatusRequest,
    request: Request,
    current_user: CurrentUser,
) -> DocumentResponse:
    document = await _get_document_service(request).set_status(
        current_user=current_user,
        document_id=document_id,
        status=payload.estado,
    )

    return _document_response(document)
