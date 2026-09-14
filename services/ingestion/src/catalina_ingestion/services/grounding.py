import re
import unicodedata

from catalina_ingestion.domain.grounding import (
    GroundingAssessment,
    GroundingFailure,
    GroundingPolicy,
    GroundingReason,
    GroundingResult,
)
from catalina_ingestion.domain.retrieval import RetrievedChunk


def normalize(text: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        text.lower(),
    )

    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )

    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            normalized,
        )
    )


def simple_stem(token: str) -> str:
    token = normalize(token)

    if token.endswith("es") and len(token) > 5:
        return token[:-2]

    if token.endswith("s") and len(token) > 4:
        return token[:-1]

    return token


def extract_years(query: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            re.findall(
                r"\b(?:19|20)\d{2}\b",
                query,
            )
        )
    )


def extract_location_anchors(
    query: str,
) -> tuple[str, ...]:
    matches = re.findall(
        (
            r"\ben\s+"
            r"([A-ZÁÉÍÓÚÑ]"
            r"[A-Za-zÁÉÍÓÚáéíóúÑñ-]+)"
            r"(?=[\s?.,]|$)"
        ),
        query,
    )

    return tuple(dict.fromkeys(matches))


def extract_service_anchors(
    query: str,
) -> tuple[str, ...]:
    matches = re.findall(
        (
            r"\bservicio\s+de\s+"
            r"([A-Za-zÁÉÍÓÚáéíóúÑñ-]+)"
        ),
        query,
        flags=re.IGNORECASE,
    )

    return tuple(dict.fromkeys(matches))


def extract_identifiers(
    query: str,
) -> tuple[str, ...]:
    matches = re.findall(
        r"\b[A-ZÁÉÍÓÚÑ]{2,}\b",
        query,
    )

    ignored = {
        "DC",
    }

    return tuple(value for value in dict.fromkeys(matches) if value not in ignored)


def extract_regulation_scopes(
    query: str,
) -> tuple[str, ...]:
    matches = re.findall(
        (
            r"\breglamento\s+"
            r"(?:"
            r"de(?:\s+(?:los|las|el|la))?"
            r"|del"
            r")\s+"
            r"([A-Za-zÁÉÍÓÚáéíóúÑñ-]+)"
        ),
        query,
        flags=re.IGNORECASE,
    )

    return tuple(dict.fromkeys(matches))


def evidence_text(
    chunks: tuple[RetrievedChunk, ...],
) -> str:
    return normalize(" ".join(chunk.text for chunk in chunks))


def scope_supported(
    target: str,
    chunks: tuple[RetrievedChunk, ...],
) -> bool:
    target_stem = simple_stem(target)

    for chunk in chunks:
        title_tokens = {simple_stem(token) for token in normalize(chunk.document_name).split()}

        if target_stem in title_tokens:
            return True

        text_tokens = normalize(chunk.text).split()

        for index, token in enumerate(text_tokens):
            if not token.startswith("reglament"):
                continue

            window = {simple_stem(value) for value in text_tokens[index : index + 9]}

            if target_stem in window:
                return True

    return False


def assess_grounding(
    query: str,
    chunks: tuple[RetrievedChunk, ...],
    policy: GroundingPolicy | None = None,
) -> GroundingResult:
    policy = policy or GroundingPolicy()

    combined = evidence_text(chunks)
    combined_tokens = set(combined.split())

    failures: list[GroundingFailure] = []

    if policy.require_years:
        for year in extract_years(query):
            if year not in combined_tokens:
                failures.append(
                    GroundingFailure(
                        GroundingReason.MISSING_YEAR,
                        year,
                    )
                )

    if policy.require_locations:
        for location in extract_location_anchors(query):
            normalized_location = normalize(location)

            if normalized_location not in combined:
                failures.append(
                    GroundingFailure(
                        GroundingReason.MISSING_LOCATION,
                        normalized_location,
                    )
                )

    if policy.require_services:
        for service in extract_service_anchors(query):
            normalized_service = normalize(service)

            if normalized_service not in combined:
                failures.append(
                    GroundingFailure(
                        GroundingReason.MISSING_SERVICE,
                        normalized_service,
                    )
                )

    if policy.require_identifiers:
        for identifier in extract_identifiers(query):
            normalized_identifier = normalize(identifier)

            if normalized_identifier not in combined_tokens:
                failures.append(
                    GroundingFailure(
                        GroundingReason.MISSING_IDENTIFIER,
                        normalized_identifier,
                    )
                )

    if policy.require_regulation_scope:
        for scope in extract_regulation_scopes(query):
            if not scope_supported(
                scope,
                chunks,
            ):
                failures.append(
                    GroundingFailure(
                        GroundingReason.UNSUPPORTED_REGULATION_SCOPE,
                        normalize(scope),
                    )
                )

    assessment = GroundingAssessment(
        supported=not failures,
        failures=tuple(failures),
        policy=policy,
    )

    return GroundingResult(
        query=query,
        chunks=chunks if assessment.supported else (),
        assessment=assessment,
    )


class GroundingGuard:
    def __init__(
        self,
        policy: GroundingPolicy | None = None,
    ) -> None:
        self.policy = policy or GroundingPolicy()

    def assess(
        self,
        query: str,
        chunks: tuple[RetrievedChunk, ...],
    ) -> GroundingResult:
        return assess_grounding(
            query,
            chunks,
            policy=self.policy,
        )
