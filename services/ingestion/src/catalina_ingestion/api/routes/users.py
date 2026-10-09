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
    User,
)
from catalina_ingestion.domain.exceptions import (
    InvalidAccessTokenError,
)
from catalina_ingestion.schemas.users import (
    ChangePasswordRequest,
    UpdateProfileRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UserListResponse,
    UserResponse,
)
from catalina_ingestion.services.auth import (
    AuthService,
)
from catalina_ingestion.services.users import (
    UserService,
)

router = APIRouter(
    tags=["users"],
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


def _get_user_service(
    request: Request,
) -> UserService:
    service = getattr(
        request.app.state,
        "user_service",
        None,
    )

    if service is None:
        raise RuntimeError("UserService no ha sido inicializado.")

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


def _user_response(
    user: User,
) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        nombre=user.nombre,
        rol=user.rol,
        activo=user.activo,
        fecha_creacion=user.fecha_creacion,
        fecha_actualizacion=(user.fecha_actualizacion),
        ultimo_acceso=user.ultimo_acceso,
    )


@router.patch(
    "/users/me",
    response_model=UserResponse,
)
async def update_profile(
    payload: UpdateProfileRequest,
    request: Request,
    current_user: CurrentUser,
) -> UserResponse:
    user = await _get_user_service(request).update_own_name(
        current_user=current_user,
        nombre=payload.nombre,
    )

    return _user_response(user)


@router.patch(
    "/users/me/password",
    status_code=204,
)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: CurrentUser,
) -> None:
    await _get_user_service(request).change_own_password(
        current_user=current_user,
        current_password=(payload.current_password),
        new_password=payload.new_password,
    )


@router.get(
    "/admin/users",
    response_model=UserListResponse,
)
async def list_users(
    request: Request,
    current_user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
) -> UserListResponse:
    users = await _get_user_service(request).list_users(
        current_user=current_user,
        limit=limit,
        offset=offset,
    )

    return UserListResponse(
        items=[_user_response(user) for user in users],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/users/{user_id}",
    response_model=UserResponse,
)
async def get_user(
    user_id: int,
    request: Request,
    current_user: CurrentUser,
) -> UserResponse:
    user = await _get_user_service(request).get_user(
        current_user=current_user,
        user_id=user_id,
    )

    return _user_response(user)


@router.patch(
    "/admin/users/{user_id}/status",
    response_model=UserResponse,
)
async def update_user_status(
    user_id: int,
    payload: UpdateUserStatusRequest,
    request: Request,
    current_user: CurrentUser,
) -> UserResponse:
    user = await _get_user_service(request).set_user_active(
        current_user=current_user,
        user_id=user_id,
        active=payload.activo,
    )

    return _user_response(user)


@router.patch(
    "/admin/users/{user_id}/role",
    response_model=UserResponse,
)
async def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    request: Request,
    current_user: CurrentUser,
) -> UserResponse:
    user = await _get_user_service(request).set_user_role(
        current_user=current_user,
        user_id=user_id,
        role=payload.rol,
    )

    return _user_response(user)
