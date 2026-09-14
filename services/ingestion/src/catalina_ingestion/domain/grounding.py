from dataclasses import dataclass
from enum import StrEnum

from catalina_ingestion.domain.retrieval import RetrievedChunk


class GroundingReason(StrEnum):
    MISSING_YEAR = "missing_year"
    MISSING_LOCATION = "missing_location"
    MISSING_SERVICE = "missing_service"
    MISSING_IDENTIFIER = "missing_identifier"
    UNSUPPORTED_REGULATION_SCOPE = "unsupported_regulation_scope"
    PASSED_GROUNDING_CHECKS = "passed_grounding_checks"


@dataclass(frozen=True, slots=True)
class GroundingPolicy:
    require_years: bool = True
    require_locations: bool = True
    require_services: bool = True
    require_identifiers: bool = True
    require_regulation_scope: bool = True

    def __post_init__(self) -> None:
        for name in (
            "require_years",
            "require_locations",
            "require_services",
            "require_identifiers",
            "require_regulation_scope",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} debe ser booleano.")


@dataclass(frozen=True, slots=True)
class GroundingFailure:
    reason: GroundingReason
    value: str

    @property
    def code(self) -> str:
        return f"{self.reason.value}:{self.value}"


@dataclass(frozen=True, slots=True)
class GroundingAssessment:
    supported: bool
    failures: tuple[GroundingFailure, ...]
    policy: GroundingPolicy

    @property
    def reasons(self) -> tuple[str, ...]:
        if self.supported:
            return (GroundingReason.PASSED_GROUNDING_CHECKS.value,)

        return tuple(failure.code for failure in self.failures)


@dataclass(frozen=True, slots=True)
class GroundingResult:
    query: str
    chunks: tuple[RetrievedChunk, ...]
    assessment: GroundingAssessment
