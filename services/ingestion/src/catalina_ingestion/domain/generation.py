from dataclasses import dataclass
from enum import StrEnum

from catalina_ingestion.domain.rag_context import ContextSource


class GenerationReason(StrEnum):
    CONVERSATIONAL = "conversational"
    GENERAL_CHAT = "general_chat"
    GENERATED = "generated"
    CACHED = "cached"
    DOCUMENT_OVERVIEW = "document_overview"
    DOCUMENT_EXCERPT = "document_excerpt"
    CAMPUS_LOCATION = "campus_location"
    DOCUMENT_IDENTIFIER_RESOLVED = "document_identifier_resolved"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INSUFFICIENT_EVIDENCE_AFTER_BUDGET = "insufficient_evidence_after_budget"
    UNSUPPORTED_GROUNDING = "unsupported_grounding"


@dataclass(frozen=True, slots=True)
class GenerationStatistics:
    total_duration_ns: int
    load_duration_ns: int
    prompt_eval_count: int
    prompt_eval_duration_ns: int
    eval_count: int
    eval_duration_ns: int

    def __post_init__(self) -> None:
        for name in (
            "total_duration_ns",
            "load_duration_ns",
            "prompt_eval_count",
            "prompt_eval_duration_ns",
            "eval_count",
            "eval_duration_ns",
        ):
            value = getattr(self, name)

            if type(value) is not int or value < 0:
                raise ValueError(f"{name} debe ser un entero mayor o igual a cero.")


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    query: str
    text: str
    generated: bool
    reason: GenerationReason
    model: str | None
    citations: tuple[ContextSource, ...]
    statistics: GenerationStatistics | None = None
    locations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("La consulta de generación no puede estar vacía.")

        if self.generated:
            if self.reason not in (GenerationReason.GENERATED, GenerationReason.GENERAL_CHAT):
                raise ValueError("Una respuesta generada debe usar un motivo de generación.")

            if not self.text.strip():
                raise ValueError("Una respuesta generada no puede tener texto vacío.")

            if not self.model or not self.model.strip():
                raise ValueError("Una respuesta generada debe indicar el modelo.")

            if self.statistics is None:
                raise ValueError("Una respuesta generada debe incluir estadísticas.")

            return

        if self.reason in (GenerationReason.GENERATED, GenerationReason.GENERAL_CHAT):
            raise ValueError("Una respuesta no generada no puede usar reason=generated.")

        if self.model is not None:
            raise ValueError("Una respuesta no generada no debe indicar un modelo.")

        if self.statistics is not None:
            raise ValueError("Una respuesta no generada no debe incluir estadísticas.")


@dataclass(frozen=True, slots=True)
class GenerationPrompt:
    system_message: str
    user_message: str
    allowed_citations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.system_message.strip():
            raise ValueError("El mensaje de sistema no puede estar vacío.")

        if not self.user_message.strip():
            raise ValueError("El mensaje de usuario no puede estar vacío.")

        if not self.allowed_citations:
            raise ValueError("El prompt debe incluir al menos una cita permitida.")

        if len(set(self.allowed_citations)) != len(self.allowed_citations):
            raise ValueError("Las citas permitidas no pueden estar duplicadas.")

        for citation in self.allowed_citations:
            if not citation.startswith("S") or not citation[1:].isdigit():
                raise ValueError(f"Identificador de cita inválido: {citation}")
