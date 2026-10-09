from decimal import Decimal

from pydantic import BaseModel


class SystemSummaryMetricsResponse(BaseModel):
    users_total: int
    users_active: int
    conversations_total: int
    messages_total: int

    documents_total: int
    documents_active: int
    documents_inactive: int

    versions_total: int
    versions_active: int
    versions_pending: int
    versions_failed: int


class IngestionMetricsResponse(BaseModel):
    jobs_total: int
    jobs_pending: int
    jobs_indexing: int
    jobs_completed: int
    jobs_failed: int
    average_progress: Decimal | None

    indexing_runs_total: int
    indexing_runs_preparing: int
    indexing_runs_indexing: int
    indexing_runs_verifying: int
    indexing_runs_active: int
    indexing_runs_failed: int


class RagMetricsResponse(BaseModel):
    messages_total: int
    messages_with_model: int
    messages_without_model: int

    average_response_time_seconds: Decimal | None

    metric_records: int
    tokens_input_total: int
    tokens_output_total: int

    average_satisfaction: Decimal | None
    average_precision: Decimal | None
