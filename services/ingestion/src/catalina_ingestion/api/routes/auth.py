from typing import Annotated

from fastapi import (
    APIRouter,
    Request,
    Response,
    Security,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
    AuthenticationResult,
    TokenRefreshResult,
)
from catalina_ingestion.domain.exceptions import (
    InvalidAccessTokenError,
)
from catalina_ingestion.schemas.auth import (
    AuthUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
)
from catalina_ingestion.services.auth import (
    AuthService,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
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


def _client_ip(
    request: Request,
) -> str | None:
    if request.client is None:
        return None

    return request.client.host


def _login_response(
    result: AuthenticationResult,
) -> LoginResponse:
    return LoginResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        refresh_expires_at=(result.refresh_expires_at),
        user=AuthUserResponse(
            id=result.user_id,
            email=result.email,
            nombre=result.nombre,
            rol=result.rol,
            activo=True,
        ),
    )


def _refresh_response(
    result: TokenRefreshResult,
) -> RefreshResponse:
    return RefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        refresh_expires_at=(result.refresh_expires_at),
    )


def _me_response(
    user: AuthenticatedUser,
) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        nombre=user.nombre,
        rol=user.rol,
        activo=user.activo,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
)
async def login(
    payload: LoginRequest,
    request: Request,
) -> LoginResponse:
    service = _get_auth_service(request)

    result = await service.authenticate(
        email=payload.email,
        password=payload.password,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return _login_response(result)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
)
async def refresh(
    payload: RefreshRequest,
    request: Request,
) -> RefreshResponse:
    service = _get_auth_service(request)

    result = await service.refresh(
        refresh_token=payload.refresh_token,
    )

    return _refresh_response(result)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    payload: LogoutRequest,
    request: Request,
) -> Response:
    service = _get_auth_service(request)

    await service.logout(
        refresh_token=payload.refresh_token,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=MeResponse,
)
async def me(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
) -> MeResponse:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise InvalidAccessTokenError

    service = _get_auth_service(request)

    user = await service.get_current_user(
        access_token=credentials.credentials,
    )

    return _me_response(user)
