from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from catalina_ingestion.services.campus import directory_answer, public_catalog

router = APIRouter(prefix="/campus", tags=["campus"])


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
