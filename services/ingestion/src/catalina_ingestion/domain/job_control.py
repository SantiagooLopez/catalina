from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class JobActionResult:
    job_id: UUID
    document_id: int
    document_version_id: int
    type: str
    state: str
