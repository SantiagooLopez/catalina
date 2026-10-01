from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
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
)
from catalina_ingestion.domain.conversations import (
    Conversation,
    Message,
)
from catalina_ingestion.domain.exceptions import (
    InvalidAccessTokenError,
)
from catalina_ingestion.schemas.conversations import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageListResponse,
    MessageResponse,
    UpdateConversationRequest,
)
from catalina_ingestion.services.auth import (
    AuthService,
)
from catalina_ingestion.services.conversations import (
    ConversationService,
)

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
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


def _get_conversation_service(
    request: Request,
) -> ConversationService:
    service = getattr(
        request.app.state,
        "conversation_service",
        None,
    )

    if service is None:
        raise RuntimeError("ConversationService no ha sido inicializado.")

    return service


async def _authenticated_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise InvalidAccessTokenError

    service = _get_auth_service(request)

    return await service.get_current_user(
        access_token=credentials.credentials,
    )


CurrentUser = Annotated[
    AuthenticatedUser,
    Depends(_authenticated_user),
]


def _conversation_response(
    conversation: Conversation,
) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        titulo=conversation.titulo,
        fecha_inicio=conversation.fecha_inicio,
        fecha_actualizacion=(conversation.fecha_actualizacion),
    )


def _message_response(
    message: Message,
) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversacion_id=message.conversacion_id,
        pregunta=message.pregunta,
        respuesta=message.respuesta,
        modelo=message.modelo,
        tiempo_respuesta=message.tiempo_respuesta,
        fecha=message.fecha,
    )


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: CreateConversationRequest,
    request: Request,
    user: CurrentUser,
) -> ConversationResponse:
    service = _get_conversation_service(request)

    conversation = await service.create_conversation(
        user_id=user.id,
        title=payload.titulo,
    )

    return _conversation_response(conversation)


@router.get(
    "",
    response_model=ConversationListResponse,
)
async def list_conversations(
    request: Request,
    user: CurrentUser,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 20,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> ConversationListResponse:
    service = _get_conversation_service(request)

    conversations = await service.list_conversations(
        user_id=user.id,
        limit=limit,
        offset=offset,
    )

    return ConversationListResponse(
        items=[_conversation_response(conversation) for conversation in conversations],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    conversation_id: int,
    request: Request,
    user: CurrentUser,
) -> ConversationResponse:
    service = _get_conversation_service(request)

    conversation = await service.get_conversation(
        user_id=user.id,
        conversation_id=(conversation_id),
    )

    return _conversation_response(conversation)


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
async def update_conversation(
    conversation_id: int,
    payload: UpdateConversationRequest,
    request: Request,
    user: CurrentUser,
) -> ConversationResponse:
    service = _get_conversation_service(request)

    conversation = await service.update_title(
        user_id=user.id,
        conversation_id=(conversation_id),
        title=payload.titulo,
    )

    return _conversation_response(conversation)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: int,
    request: Request,
    user: CurrentUser,
) -> Response:
    service = _get_conversation_service(request)

    await service.delete_conversation(
        user_id=user.id,
        conversation_id=(conversation_id),
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def list_messages(
    conversation_id: int,
    request: Request,
    user: CurrentUser,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> MessageListResponse:
    service = _get_conversation_service(request)

    messages = await service.list_messages(
        user_id=user.id,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )

    return MessageListResponse(
        items=[_message_response(message) for message in messages],
        limit=limit,
        offset=offset,
    )
