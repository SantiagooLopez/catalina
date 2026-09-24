import re
from dataclasses import dataclass

from catalina_ingestion.domain.rag_context import (
    ContextSource,
    RagContext,
)
from catalina_ingestion.services.action_anchor_reranker import (
    extract_action_stems,
    normalize_anchor_text,
)

IDENTIFIER_QUERY_PATTERN = re.compile(
    r"\b(?:que|cual)\s+"
    r"(acuerdo|resolucion|documento|version|acto|circular|decreto)\b"
)


@dataclass(frozen=True, slots=True)
class DocumentIdentifierResolution:
    identifier_kind: str
    identifier: str
    citation_id: str
    matched_actions: frozenset[str]
    source: ContextSource


class DocumentIdentifierResolver:
    def resolve(
        self,
        context: RagContext,
    ) -> DocumentIdentifierResolution | None:
        if not context.enabled:
            return None

        if not context.sources:
            return None

        normalized_query = normalize_anchor_text(context.query)

        identifier_match = IDENTIFIER_QUERY_PATTERN.search(normalized_query)

        if identifier_match is None:
            return None

        query_actions = extract_action_stems(context.query)

        if not query_actions:
            return None

        primary_source = context.sources[0]

        source_actions = extract_action_stems(primary_source.document_name) | extract_action_stems(
            primary_source.section
        )

        matched_actions = query_actions & source_actions

        if not matched_actions:
            return None

        identifier = primary_source.version.strip()

        if not identifier:
            return None

        return DocumentIdentifierResolution(
            identifier_kind=identifier_match.group(1),
            identifier=identifier,
            citation_id=primary_source.citation_id,
            matched_actions=matched_actions,
            source=primary_source,
        )
