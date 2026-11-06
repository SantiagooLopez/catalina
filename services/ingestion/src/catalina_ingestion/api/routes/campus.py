from fastapi import APIRouter, HTTPException, Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from catalina_ingestion.domain.exceptions import InvalidAccessTokenError
from pydantic import BaseModel, Field, field_validator

from catalina_ingestion.services.campus import directory_answer, public_catalog

_bearer = HTTPBearer(auto_error=False)


async def require_campus_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Security(_bearer)):
    if credentials is None or credentials.scheme.lower() != 'bearer' or not credentials.credentials:
        raise InvalidAccessTokenError
    return await request.app.state.auth_service.get_current_user(access_token=credentials.credentials)


router = APIRouter(prefix="/campus", tags=["campus"], dependencies=[Depends(require_campus_user)])


class CampusQuestion(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    selected_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9-]+$")

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Escribe una pregunta sobre el mapa.")
        return value.strip()


class CampusReply(BaseModel):
    query: str
    text: str
    locations: list[str]
    reason: str


@router.get("/locations")
async def locations() -> dict:
    return public_catalog()


@router.post("/query", response_model=CampusReply)
async def question(payload: CampusQuestion) -> CampusReply:
    try:
        answer = directory_answer(payload.query, selected_id=payload.selected_id, force=True)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return CampusReply(
        query=answer.query, text=answer.text,
        locations=list(answer.locations), reason=answer.reason,
    )
