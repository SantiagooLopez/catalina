from uuid import UUID

import pytest

from catalina_ingestion.core.config import Settings
from catalina_ingestion.domain.embeddings import (
    EmbeddedChunk,
    EmbeddedDocument,
    EmbeddingStatistics,
)
from catalina_ingestion.domain.exceptions import IndexingError
from catalina_ingestion.domain.indexing import IndexingContext
from catalina_ingestion.domain.processed import (
    DocumentChunk,
    ProcessedDocument,
)
from catalina_ingestion.services.qdrant_indexing import (
    QdrantIndexingService,
)


def create_settings() -> Settings:
    return Settings(
        database_password="password-for-tests",
        embedding_dimension=3,
    )


def create_data():
    chunk = DocumentChunk(
        index=0,
        text="Información institucional.",
        section="Información",
        page_start=1,
        page_end=1,
        source_block_indexes=(0,),
        character_count=26,
        estimated_tokens=5,
        text_sha256="a" * 64,
    )

    processed = ProcessedDocument(
        title="Documento",
        page_count=1,
        blocks=[],
        chunks=[chunk],
        content_sha256="b" * 64,
        removed_repeated_blocks=0,
    )

    embedded = EmbeddedDocument(
        model="embeddinggemma:latest",
        dimension=3,
        chunks=[
            EmbeddedChunk(
                chunk=chunk,
                vector=(0.1, 0.2, 0.3),
            )
        ],
        statistics=EmbeddingStatistics(
            batch_count=1,
            input_count=1,
            total_duration_ns=1,
            load_duration_ns=1,
            prompt_eval_count=5,
        ),
    )

    context = IndexingContext(
        document_id=1,
        document_version_id=1,
        ingestion_job_id=UUID("11111111-1111-1111-1111-111111111111"),
        document_name="Documento",
        version="1.0",
        category="faq",
        language="es",
        source_file="documento.txt",
    )

    return context, processed, embedded


def test_builds_deterministic_point_ids():
    context, processed, embedded = create_data()
    service = QdrantIndexingService(settings=create_settings())
    run_id = UUID("22222222-2222-2222-2222-222222222222")

    first_points, first_manifests = service._build_points(
        context,
        processed,
        embedded,
        run_id,
    )
    second_points, second_manifests = service._build_points(
        context,
        processed,
        embedded,
        run_id,
    )

    assert first_points[0].id == second_points[0].id
    assert first_manifests[0].point_id == second_manifests[0].point_id


def test_payload_contains_traceability():
    context, processed, embedded = create_data()
    service = QdrantIndexingService(settings=create_settings())

    points, _ = service._build_points(
        context,
        processed,
        embedded,
        UUID("22222222-2222-2222-2222-222222222222"),
    )

    payload = points[0].payload

    assert payload["document_id"] == 1
    assert payload["document_version_id"] == 1
    assert payload["page_start"] == 1
    assert payload["text"] == "Información institucional."


def test_rejects_incorrect_dimension():
    _, processed, embedded = create_data()
    service = QdrantIndexingService(
        settings=Settings(
            database_password="password-for-tests",
            embedding_dimension=768,
        )
    )

    with pytest.raises(IndexingError) as captured:
        service._validate_inputs(processed, embedded)

    assert captured.value.code == "INDEX_DIMENSION_MISMATCH"
