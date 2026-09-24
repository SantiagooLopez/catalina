import re
import unicodedata
from dataclasses import dataclass

from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationPrompt,
)
from catalina_ingestion.domain.rag_context import RagContext

IDENTIFIER_QUERY_PATTERN = re.compile(
    r"\b(?:que|cual)\s+"
    r"(?:acuerdo|resolucion|documento|version|acto|circular|decreto)\b"
)


@dataclass(frozen=True, slots=True)
class GenerationVerification:
    valid: bool
    reason: str
    required_identifier: str | None = None
    primary_citation: str | None = None


class GenerationVerifier:
    def verify(
        self,
        *,
        context: RagContext,
        answer: GeneratedAnswer,
    ) -> GenerationVerification:
        if not context.enabled or not answer.generated:
            return GenerationVerification(
                valid=True,
                reason="verification_not_required",
            )

        if not self._asks_for_identifier(context.query):
            return GenerationVerification(
                valid=True,
                reason="passed",
            )

        if not context.sources:
            return GenerationVerification(
                valid=False,
                reason="missing_primary_source",
            )

        primary_source = context.sources[0]
        identifier = primary_source.version.strip()

        if not identifier:
            return GenerationVerification(
                valid=False,
                reason="missing_primary_identifier",
                primary_citation=primary_source.citation_id,
            )

        if self._contains_identifier(
            answer.text,
            identifier,
        ):
            return GenerationVerification(
                valid=True,
                reason="passed",
                required_identifier=identifier,
                primary_citation=primary_source.citation_id,
            )

        return GenerationVerification(
            valid=False,
            reason="missing_primary_identifier",
            required_identifier=identifier,
            primary_citation=primary_source.citation_id,
        )

    def build_correction_prompt(
        self,
        *,
        original_prompt: GenerationPrompt,
        previous_answer: str,
        verification: GenerationVerification,
    ) -> GenerationPrompt:
        if verification.valid:
            raise ValueError("No se puede corregir una respuesta que ya fue validada.")

        if not verification.required_identifier:
            raise ValueError("La corrección requiere un identificador documental.")

        if not verification.primary_citation:
            raise ValueError("La corrección requiere una fuente principal.")

        correction = (
            "\n\n"
            "CORRECCIÓN OBLIGATORIA:\n"
            "La respuesta anterior no cumplió el contrato factual.\n\n"
            "RESPUESTA ANTERIOR:\n"
            f"{previous_answer}\n\n"
            "DATO DOCUMENTAL OBLIGATORIO:\n"
            f"Fuente principal: "
            f"[{verification.primary_citation}]\n"
            "Identificador/versión documental: "
            f"{verification.required_identifier}\n\n"
            "Reescribe la respuesta completa. "
            "Debes identificar explícitamente este documento "
            "como respuesta cuando corresponda a la pregunta. "
            "No sustituyas este identificador por acuerdos, "
            "resoluciones o documentos mencionados únicamente "
            "como antecedentes dentro de otras fuentes. "
            "Usa solamente las citas permitidas."
        )

        return GenerationPrompt(
            system_message=original_prompt.system_message,
            user_message=(original_prompt.user_message + correction),
            allowed_citations=original_prompt.allowed_citations,
        )

    @staticmethod
    def _asks_for_identifier(
        query: str,
    ) -> bool:
        normalized = _normalize_text(query)
        return IDENTIFIER_QUERY_PATTERN.search(normalized) is not None

    @staticmethod
    def _contains_identifier(
        text: str,
        identifier: str,
    ) -> bool:
        normalized_text = _normalize_text(text)
        normalized_identifier = _normalize_text(identifier)

        match = re.fullmatch(
            r"\s*(\d+)\s*[-/]\s*(\d{4})\s*",
            normalized_identifier,
        )

        if match is None:
            return normalized_identifier in normalized_text

        number = match.group(1)
        year = match.group(2)

        canonical_number = str(int(number))

        pattern = re.compile(
            rf"(?<!\d)"
            rf"0*{re.escape(canonical_number)}"
            rf"\s*(?:(?:-|/)|(?:de|del))?\s*"
            rf"{re.escape(year)}"
            rf"(?!\d)"
        )

        return pattern.search(normalized_text) is not None


def _normalize_text(
    value: str,
) -> str:
    decomposed = unicodedata.normalize(
        "NFKD",
        value.casefold(),
    )

    return "".join(character for character in decomposed if not unicodedata.combining(character))
