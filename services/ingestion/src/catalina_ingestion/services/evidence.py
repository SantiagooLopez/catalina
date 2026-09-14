import math

from catalina_ingestion.domain.evidence import (
    EvidenceAssessment,
    EvidencePolicy,
    EvidenceReason,
    EvidenceResult,
)
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.domain.search import SearchError
from catalina_ingestion.domain.selection import SelectedSearchResult
from catalina_ingestion.services.retrieval_selection import (
    RetrievalSelectionService,
    canonical_text,
)


def assess_evidence(
    selected: SelectedSearchResult,
    policy: EvidencePolicy | None = None,
) -> EvidenceResult:
    policy = policy or EvidencePolicy()

    for chunk in selected.chunks:
        if not math.isfinite(chunk.score):
            raise SearchError(f"Score no finito en el punto {chunk.point_id}.")

        if not canonical_text(chunk.text):
            raise SearchError(f"Texto vacío en el punto {chunk.point_id}.")

    relevant = tuple(
        chunk for chunk in selected.chunks if chunk.score >= policy.minimum_chunk_score
    )

    best_score = max(
        (chunk.score for chunk in relevant),
        default=None,
    )
    document_count = len({chunk.document_id for chunk in relevant})

    # Evita que textos repetidos inflen el conteo de caracteres.
    unique_texts = {canonical_text(chunk.text) for chunk in relevant}
    character_count = sum(len(text) for text in unique_texts)

    reasons: list[EvidenceReason] = []

    if not selected.chunks:
        reasons.append(EvidenceReason.NO_RESULTS)
    elif not relevant:
        reasons.append(EvidenceReason.NO_RELEVANT_CHUNKS)
    else:
        if best_score < policy.minimum_best_score:
            reasons.append(EvidenceReason.LOW_BEST_SCORE)

        if len(relevant) < policy.minimum_chunks:
            reasons.append(EvidenceReason.TOO_FEW_CHUNKS)

        if document_count < policy.minimum_documents:
            reasons.append(EvidenceReason.TOO_FEW_DOCUMENTS)

        if character_count < policy.minimum_characters:
            reasons.append(EvidenceReason.TOO_LITTLE_TEXT)

    sufficient = not reasons

    if sufficient:
        reasons.append(EvidenceReason.PASSED_RETRIEVAL_CHECKS)

    assessment = EvidenceAssessment(
        evidence_sufficient=sufficient,
        reasons=tuple(reasons),
        evaluated_chunks=selected.count,
        relevant_chunks=len(relevant),
        document_count=document_count,
        character_count=character_count,
        best_score=best_score,
        policy=policy,
    )

    return EvidenceResult(
        query=selected.query,
        # Solo se habilita contexto cuando supera las reglas.
        chunks=relevant if sufficient else (),
        assessment=assessment,
    )


class EvidenceRetrievalService:
    def __init__(
        self,
        selection_service: RetrievalSelectionService | None = None,
        policy: EvidencePolicy | None = None,
    ) -> None:
        self.selection_service = selection_service or RetrievalSelectionService()
        self.policy = policy or EvidencePolicy()

    async def search(
        self,
        query: RetrievalQuery,
    ) -> EvidenceResult:
        selected = await self.selection_service.search(query)

        return assess_evidence(
            selected=selected,
            policy=self.policy,
        )
