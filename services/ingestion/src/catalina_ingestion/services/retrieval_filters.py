from collections.abc import Sequence

from qdrant_client import models

from catalina_ingestion.domain.retrieval_filters import RetrievalFilter


def build_retrieval_filter(
    run_ids: Sequence[str],
    model: str,
    filters: RetrievalFilter | None,
) -> models.Filter:
    if not run_ids:
        raise ValueError("No se puede buscar sin ejecuciones autorizadas.")

    conditions = [
        models.FieldCondition(
            key="index_run_id",
            match=models.MatchAny(any=list(run_ids)),
        ),
        models.FieldCondition(
            key="embedding_model",
            match=models.MatchValue(value=model),
        ),
    ]

    if filters is not None:
        for name in (
            "document_id",
            "document_version_id",
            "category",
            "language",
            "version",
            "section",
        ):
            value = getattr(filters, name)

            if value is not None:
                conditions.append(
                    models.FieldCondition(
                        key=name,
                        match=models.MatchValue(value=value),
                    )
                )

        # Intersección entre el rango del fragmento y el solicitado.
        if filters.page_from is not None:
            conditions.append(
                models.FieldCondition(
                    key="page_end",
                    range=models.Range(gte=filters.page_from),
                )
            )

        if filters.page_to is not None:
            conditions.append(
                models.FieldCondition(
                    key="page_start",
                    range=models.Range(lte=filters.page_to),
                )
            )

    return models.Filter(must=conditions)
