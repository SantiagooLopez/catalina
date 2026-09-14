import asyncio
from contextlib import AsyncExitStack

from catalina_ingestion.clients.ollama import (
    close_ollama_client,
    open_ollama_client,
)
from catalina_ingestion.clients.qdrant import (
    close_qdrant_client,
    open_qdrant_client,
)
from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
)
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.evidence import EvidenceRetrievalService


async def main():
    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        service = EvidenceRetrievalService()

        for threshold in (0.0, 0.70):
            result = await service.search(
                RetrievalQuery(
                    query=("¿Dónde puedo consultar el reglamento institucional?"),
                    score_threshold=threshold,
                )
            )

            assessment = result.assessment

            print(f"umbral_busqueda={threshold}")
            print(f"evidencia_suficiente={assessment.evidence_sufficient}")
            print("motivos=" + ",".join(reason.value for reason in assessment.reasons))
            print(f"evaluados={assessment.evaluated_chunks}")
            print(f"relevantes={assessment.relevant_chunks}")
            print(f"documentos={assessment.document_count}")
            print(f"caracteres={assessment.character_count}")
            print(f"contexto_habilitado={len(result.chunks)}")
            print()

        print("EVALUACIÓN DE EVIDENCIA: EJECUTADA")


if __name__ == "__main__":
    asyncio.run(main())
