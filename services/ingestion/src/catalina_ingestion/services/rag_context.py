import json
from dataclasses import asdict

from catalina_ingestion.domain.evidence import EvidenceResult
from catalina_ingestion.domain.rag_context import ContextSource, RagContext
from catalina_ingestion.domain.retrieval import RetrievalQuery, RetrievedChunk
from catalina_ingestion.domain.selection import SelectedSearchResult
from catalina_ingestion.services.evidence import (
    EvidenceRetrievalService,
    assess_evidence,
)
from catalina_ingestion.services.grounding import GroundingGuard


def make_source(
    chunk: RetrievedChunk,
    citation_number: int,
) -> ContextSource:
    return ContextSource(
        citation_id=f"S{citation_number}",
        point_id=chunk.point_id,
        document_id=chunk.document_id,
        document_version_id=chunk.document_version_id,
        document_name=chunk.document_name,
        version=chunk.version,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        section=chunk.section,
        index_run_id=chunk.metadata.get("index_run_id"),
    )


def render_context(
    chunks: list[RetrievedChunk],
) -> tuple[str, tuple[ContextSource, ...]]:
    sources = tuple(
        make_source(chunk, index)
        for index, chunk in enumerate(
            chunks,
            start=1,
        )
    )

    records = [
        {
            "source": asdict(source),
            "text": chunk.text,
        }
        for source, chunk in zip(
            sources,
            chunks,
            strict=True,
        )
    ]

    text = json.dumps(
        {"sources": records},
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return text, sources


class ContextBuilder:
    def __init__(
        self,
        max_context_characters: int = 12000,
    ) -> None:
        if type(max_context_characters) is not int or max_context_characters < 1:
            raise ValueError("max_context_characters debe ser un entero positivo.")

        self.max_context_characters = max_context_characters

    def build(
        self,
        evidence: EvidenceResult,
        grounding_guard: GroundingGuard | None = None,
    ) -> RagContext:
        if not evidence.assessment.evidence_sufficient:
            return RagContext(
                query=evidence.query,
                enabled=False,
                reason="insufficient_evidence",
                text="",
                sources=(),
                character_count=0,
                omitted_by_budget=0,
                assessment=evidence.assessment,
            )

        kept: list[RetrievedChunk] = []
        omitted = 0

        # Conserva el orden de relevancia recibido.
        # Si uno no cabe, comprueba si caben
        # los siguientes.
        for chunk in evidence.chunks:
            proposed = [
                *kept,
                chunk,
            ]

            proposed_text, _ = render_context(proposed)

            if len(proposed_text) <= self.max_context_characters:
                kept.append(chunk)
            else:
                omitted += 1

        remaining = SelectedSearchResult(
            query=evidence.query,
            chunks=tuple(kept),
            candidate_count=len(kept),
            removed_by_threshold=0,
            removed_by_top_k=0,
        )

        checked = assess_evidence(
            remaining,
            policy=evidence.assessment.policy,
        )

        if not checked.assessment.evidence_sufficient:
            return RagContext(
                query=evidence.query,
                enabled=False,
                reason=("insufficient_evidence_after_budget"),
                text="",
                sources=(),
                character_count=0,
                omitted_by_budget=omitted,
                assessment=checked.assessment,
            )

        grounding_assessment = None

        if grounding_guard is not None:
            grounding = grounding_guard.assess(
                checked.query,
                checked.chunks,
            )

            grounding_assessment = grounding.assessment

            if not grounding.assessment.supported:
                return RagContext(
                    query=checked.query,
                    enabled=False,
                    reason=("unsupported_grounding"),
                    text="",
                    sources=(),
                    character_count=0,
                    omitted_by_budget=omitted,
                    assessment=checked.assessment,
                    grounding=(grounding.assessment),
                )

        text, sources = render_context(list(checked.chunks))

        return RagContext(
            query=checked.query,
            enabled=True,
            reason="ready",
            text=text,
            sources=sources,
            character_count=len(text),
            omitted_by_budget=omitted,
            assessment=checked.assessment,
            grounding=grounding_assessment,
        )


class RagContextService:
    def __init__(
        self,
        evidence_service: (EvidenceRetrievalService | None) = None,
        builder: ContextBuilder | None = None,
        grounding_guard: (GroundingGuard | None) = None,
    ) -> None:
        self.evidence_service = evidence_service or EvidenceRetrievalService()

        self.builder = builder or ContextBuilder()

        # Mientras validamos la integración,
        # None mantiene exactamente el
        # comportamiento anterior.
        self.grounding_guard = grounding_guard

    async def build(
        self,
        query: RetrievalQuery,
    ) -> RagContext:
        evidence = await self.evidence_service.search(query)

        return self.builder.build(
            evidence,
            grounding_guard=(self.grounding_guard),
        )
