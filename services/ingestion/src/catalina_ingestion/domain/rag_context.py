from dataclasses import dataclass

from catalina_ingestion.domain.evidence import EvidenceAssessment
from catalina_ingestion.domain.grounding import GroundingAssessment


@dataclass(frozen=True, slots=True)
class ContextSource:
    citation_id: str
    point_id: str
    document_id: int
    document_version_id: int
    document_name: str
    version: str
    page_start: int | None
    page_end: int | None
    section: str | None
    index_run_id: str | None


@dataclass(frozen=True, slots=True)
class RagContext:
    query: str
    enabled: bool
    reason: str
    text: str
    sources: tuple[ContextSource, ...]
    character_count: int
    omitted_by_budget: int
    assessment: EvidenceAssessment
    grounding: GroundingAssessment | None = None
