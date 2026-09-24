import asyncio
from collections.abc import Sequence
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
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationPrompt,
    GenerationReason,
)
from catalina_ingestion.domain.rag_context import ContextSource
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.answer_generation import (
    AnswerGenerationService,
)
from catalina_ingestion.services.generation import GenerationService


class CountingGenerationService(GenerationService):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def generate(
        self,
        *,
        query: str,
        prompt: GenerationPrompt,
        citations: Sequence[ContextSource],
    ) -> GeneratedAnswer:
        self.calls += 1

        return await super().generate(
            query=query,
            prompt=prompt,
            citations=citations,
        )


def page_label(source: ContextSource) -> str:
    if source.page_start is None:
        return "N/D"

    if source.page_end is None or source.page_end == source.page_start:
        return str(source.page_start)

    return f"{source.page_start}-{source.page_end}"


def print_sources(
    answer: GeneratedAnswer,
) -> None:
    if not answer.citations:
        print("fuentes=[]")
        return

    print("fuentes:")

    for source in answer.citations:
        print(
            f"  [{source.citation_id}] "
            f"documento={source.document_name!r} "
            f"version={source.version!r} "
            f"pagina={page_label(source)} "
            f"seccion={source.section!r}"
        )


async def main() -> None:
    generation_service = CountingGenerationService()

    service = AnswerGenerationService(
        generation_service=generation_service,
    )

    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)

        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)

        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)

        print()
        print("========================================")
        print(" FASE 6.8 - SAFE ANSWER END-TO-END")
        print("========================================")

        positive_query = RetrievalQuery(
            query=("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?")
        )

        positive = await service.answer(positive_query)

        print()
        print("========================================")
        print(" CASO IDENTIFICADOR DOCUMENTAL")
        print("========================================")
        print(f"generated={positive.generated}")
        print(f"reason={positive.reason.value}")
        print(f"model={positive.model}")
        print(f"statistics={positive.statistics}")
        print(f"llm_calls={generation_service.calls}")
        print()
        print("respuesta:")
        print(positive.text)
        print()
        print_sources(positive)

        if positive.generated:
            raise RuntimeError("La respuesta documental no debía ser generada por Llama.")

        if positive.reason is not GenerationReason.DOCUMENT_IDENTIFIER_RESOLVED:
            raise RuntimeError(
                "La respuesta debía resolverse mediante document_identifier_resolved."
            )

        if positive.model is not None:
            raise RuntimeError("Una respuesta determinista no debe indicar modelo LLM.")

        if positive.statistics is not None:
            raise RuntimeError("Una respuesta determinista no debe tener estadísticas LLM.")

        if not positive.citations:
            raise RuntimeError("La respuesta documental no devolvió fuente.")

        if positive.citations[0].version != "050-2026":
            raise RuntimeError("La fuente principal no corresponde a 050-2026.")

        if "050-2026" not in positive.text:
            raise RuntimeError("La respuesta no identifica 050-2026.")

        if "[S1]" not in positive.text:
            raise RuntimeError("La respuesta documental no contiene [S1].")

        if generation_service.calls != 0:
            raise RuntimeError("Llama no debía ejecutarse para la resolución documental.")

        calls_after_positive = generation_service.calls

        negative_query = RetrievalQuery(
            query=("¿Dónde queda la sede de la Universidad Católica de Colombia en Cali?")
        )

        negative = await service.answer(negative_query)

        print()
        print("========================================")
        print(" CASO SIN GROUNDING")
        print("========================================")
        print(f"generated={negative.generated}")
        print(f"reason={negative.reason.value}")
        print(f"model={negative.model}")
        print(f"statistics={negative.statistics}")
        print(f"llm_calls={generation_service.calls}")
        print()
        print("respuesta:")
        print(negative.text)

        if negative.generated:
            raise RuntimeError("El caso negativo no debía generar respuesta.")

        if negative.reason is not GenerationReason.UNSUPPORTED_GROUNDING:
            raise RuntimeError("El caso negativo debía ser rechazado por unsupported_grounding.")

        if negative.model is not None:
            raise RuntimeError("Un caso rechazado no debe indicar modelo.")

        if negative.statistics is not None:
            raise RuntimeError("Un caso rechazado no debe tener estadísticas de generación.")

        if generation_service.calls != calls_after_positive:
            raise RuntimeError("Llama fue llamado para una pregunta sin grounding suficiente.")

        print()
        print("========================================")
        print(" RESULTADO")
        print("========================================")
        print("IDENTIFICADOR DOCUMENTAL: PASS ✅")
        print("050-2026: PASS ✅")
        print("LLM OMITIDO EN RESOLUCIÓN: PASS ✅")
        print("NEGATIVO: PASS ✅")
        print("LLM BLOQUEADO SIN GROUNDING: PASS ✅")
        print()
        print("SAFE ANSWER END-TO-END: PASS ✅")


if __name__ == "__main__":
    asyncio.run(main())
