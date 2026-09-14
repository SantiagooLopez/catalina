from catalina_ingestion.domain.evidence import EvidencePolicy
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.action_anchor_reranker import (
    ActionAnchorReranker,
)
from catalina_ingestion.services.grounding import GroundingGuard
from catalina_ingestion.services.retrieval_runtime import (
    ManagedRetrievalService,
)


def test_production_retrieval_threshold_defaults():
    query = RetrievalQuery(query="Consulta institucional")

    policy = EvidencePolicy()

    assert query.score_threshold == 0.50
    assert policy.minimum_chunk_score == 0.50
    assert policy.minimum_best_score == 0.54


def test_managed_retrieval_enables_validated_stack_by_default():
    service = ManagedRetrievalService()

    context_service = service.context_service
    evidence_service = context_service.evidence_service
    selection_service = evidence_service.selection_service

    assert isinstance(
        context_service.grounding_guard,
        GroundingGuard,
    )

    assert isinstance(
        selection_service.reranker,
        ActionAnchorReranker,
    )

    assert selection_service.reranker.bonus == 0.15

    assert evidence_service.policy.minimum_chunk_score == 0.50

    assert evidence_service.policy.minimum_best_score == 0.54
