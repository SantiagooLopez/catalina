import hashlib
from collections import OrderedDict
from dataclasses import replace
from time import monotonic

from catalina_ingestion.core.config import get_settings
from catalina_ingestion.domain.exceptions import GenerationError
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationReason,
)
from catalina_ingestion.domain.rag_context import RagContext
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.conversation_routing import conversational_reply
from catalina_ingestion.services.document_excerpt import resolve_excerpt
from catalina_ingestion.services.document_identifier_resolver import (
    DocumentIdentifierResolution,
    DocumentIdentifierResolver,
)
from catalina_ingestion.services.document_overview import resolve_overview
from catalina_ingestion.services.generation import GenerationService
from catalina_ingestion.services.generation_verifier import (
    GenerationVerifier,
)
from catalina_ingestion.services.prompt_builder import PromptBuilder
from catalina_ingestion.services.retrieval_runtime import (
    ManagedRetrievalService,
)

REJECTED_ANSWER_TEXT = (
    "No encontré evidencia institucional suficiente para responder esta pregunta con seguridad."
)


class AnswerGenerationService:
    def __init__(
        self,
        retrieval_service: ManagedRetrievalService | None = None,
        prompt_builder: PromptBuilder | None = None,
        generation_service: GenerationService | None = None,
        verifier: GenerationVerifier | None = None,
        identifier_resolver: DocumentIdentifierResolver | None = None,
        document_response_mode: str | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service or ManagedRetrievalService()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.generation_service = generation_service or GenerationService()
        self.verifier = verifier or GenerationVerifier()
        self.identifier_resolver = identifier_resolver or DocumentIdentifierResolver()
        self._cache: OrderedDict[str, tuple[float, GeneratedAnswer]] = OrderedDict()
        self.document_response_mode = (
            document_response_mode or get_settings().document_response_mode
        )

    async def answer(
        self,
        query: RetrievalQuery,
    ) -> GeneratedAnswer:
        reply = conversational_reply(query.query)
        if reply is not None:
            return GeneratedAnswer(
                query=query.query, text=reply, generated=False,
                reason=GenerationReason.CONVERSATIONAL, model=None, citations=(),
            )
        context = await self.retrieval_service.build(query)

        if not context.enabled:
            return self._rejected_answer(context)

        # Fresh retrieval already rechecked active runs. Changed evidence invalidates the key.
        cache_key = hashlib.sha256((context.query + "\0" + context.text).encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is not None and monotonic() - cached[0] < 600:
            self._cache.move_to_end(cache_key)
            return replace(
                cached[1], generated=False, reason=GenerationReason.CACHED,
                model=None, statistics=None,
            )

        if self.document_response_mode == "extractive":
            overview = resolve_overview(context)
            if overview is not None:
                return overview
            excerpt = resolve_excerpt(context)
            if excerpt is not None:
                return excerpt

        identifier_resolution = self.identifier_resolver.resolve(context)

        if identifier_resolution is not None:
            return self._identifier_answer(
                context=context,
                resolution=identifier_resolution,
            )

        prompt = self.prompt_builder.build(context)

        answer = await self.generation_service.generate(
            query=context.query,
            prompt=prompt,
            citations=context.sources,
        )

        verification = self.verifier.verify(
            context=context,
            answer=answer,
        )

        if verification.valid:
            self._remember(cache_key, answer)
            return answer

        correction_prompt = self.verifier.build_correction_prompt(
            original_prompt=prompt,
            previous_answer=answer.text,
            verification=verification,
        )

        corrected_answer = await self.generation_service.generate(
            query=context.query,
            prompt=correction_prompt,
            citations=context.sources,
        )

        corrected_verification = self.verifier.verify(
            context=context,
            answer=corrected_answer,
        )

        if corrected_verification.valid:
            self._remember(cache_key, corrected_answer)
            return corrected_answer

        raise GenerationError(
            "GENERATION_VERIFICATION_FAILED",
            ("La respuesta generada no superó la validación factual."),
            {
                "first_reason": verification.reason,
                "final_reason": (corrected_verification.reason),
                "required_identifier": (corrected_verification.required_identifier),
                "primary_citation": (corrected_verification.primary_citation),
            },
        )

    def _remember(self, key: str, answer: GeneratedAnswer) -> None:
        self._cache[key] = (monotonic(), answer)
        self._cache.move_to_end(key)
        while len(self._cache) > 64:
            self._cache.popitem(last=False)

    @staticmethod
    def _identifier_answer(
        *,
        context: RagContext,
        resolution: DocumentIdentifierResolution,
    ) -> GeneratedAnswer:
        text = (
            f"El {resolution.identifier_kind} identificado "
            "en la fuente institucional principal corresponde "
            f"al identificador documental "
            f"{resolution.identifier}. "
            f"[{resolution.citation_id}]"
        )

        return GeneratedAnswer(
            query=context.query,
            text=text,
            generated=False,
            reason=(GenerationReason.DOCUMENT_IDENTIFIER_RESOLVED),
            model=None,
            citations=(resolution.source,),
            statistics=None,
        )

    @staticmethod
    def _rejected_answer(
        context: RagContext,
    ) -> GeneratedAnswer:
        reason = _map_rejection_reason(context.reason)

        return GeneratedAnswer(
            query=context.query,
            text=REJECTED_ANSWER_TEXT,
            generated=False,
            reason=reason,
            model=None,
            citations=(),
            statistics=None,
        )


def _map_rejection_reason(
    reason: str,
) -> GenerationReason:
    mapping = {
        "insufficient_evidence": (GenerationReason.INSUFFICIENT_EVIDENCE),
        "insufficient_evidence_after_budget": (GenerationReason.INSUFFICIENT_EVIDENCE_AFTER_BUDGET),
        "unsupported_grounding": (GenerationReason.UNSUPPORTED_GROUNDING),
    }

    try:
        return mapping[reason]
    except KeyError as error:
        raise ValueError(f"Motivo de rechazo RAG no soportado: {reason}") from error
