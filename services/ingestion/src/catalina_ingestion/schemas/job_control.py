from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class ReindexRequest(BaseModel):
    reason: str = Field(
        min_length=3,
        max_length=500,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("La razón no puede estar vacía.")

        return cleaned


class JobActionResponse(BaseModel):
    job_id: UUID
    document_id: int
    document_version_id: int
    type: str
    state: str
