"""Expand title-only matches and document overviews within the same active index run."""

import json
import re
import unicodedata
from dataclasses import asdict, replace

from qdrant_client import models

from catalina_ingestion.clients.qdrant import get_qdrant_client
from catalina_ingestion.core.config import get_settings
from catalina_ingestion.domain.rag_context import ContextSource, RagContext
from catalina_ingestion.domain.search import IndexedPayload, SearchError
from catalina_ingestion.repositories.retrieval import RetrievalRepository


def is_overview(query: str) -> bool:
    text = "".join(c for c in unicodedata.normalize("NFKD", query.casefold())
                   if not unicodedata.combining(c))
    if re.search(
        r"\b(?:articulo|capitulo|derechos?|deberes?|faltas?|sanciones?|matricula)\b", text,
    ):
        return False
    return bool(re.search(
        r"\b(?:de que trata|en que consiste|resum\w*|vision general|que contiene|"
        r"que temas|explicame el|explicame la)\b", text,
    ))


class EvidenceExpansionService:
    async def expand(self, context: RagContext) -> RagContext:
        if not context.enabled or not context.sources:
            return context
        records = json.loads(context.text).get("sources", [])
        if not records:
            return context
        overview = is_overview(context.query)
        normalized = "".join(c for c in unicodedata.normalize("NFKD", context.query.casefold())
                             if not unicodedata.combining(c))
        focused = [term for term in ("derech", "deber", "falta", "sancion", "matricul")
                   if term in normalized]
        if not overview and not focused and not any(
            len(r["text"].strip()) < 100 for r in records
        ):
            return context

        settings = get_settings()
        repository = RetrievalRepository()
        runs = await repository.active_runs(settings)
        primary = context.sources[0]
        identity = (primary.document_id, primary.document_version_id)
        if runs.get(primary.index_run_id) != identity:
            return replace(
                context, enabled=False, reason="insufficient_evidence", text="", sources=(),
            )
        scope = models.Filter(must=[
            models.FieldCondition(key="index_run_id", match=models.MatchValue(
                value=primary.index_run_id)),
            models.FieldCondition(key="document_id", match=models.MatchValue(
                value=primary.document_id)),
            models.FieldCondition(key="document_version_id", match=models.MatchValue(
                value=primary.document_version_id)),
            models.FieldCondition(key="embedding_model", match=models.MatchValue(
                value=settings.ollama_embedding_model)),
        ])
        # Bounded scan of one already matched document, not the entire collection.
        points, _ = await get_qdrant_client().scroll(
            collection_name=settings.qdrant_collection, scroll_filter=scope,
            limit=256, with_payload=True, with_vectors=False,
        )
        candidates = []
        for point in points:
            item = IndexedPayload.model_validate(point.payload or {})
            if (item.index_run_id != primary.index_run_id
                    or (item.document_id, item.document_version_id) != identity
                    or item.embedding_model != settings.ollama_embedding_model):
                raise SearchError("La ampliación salió del documento autorizado.")
            candidates.append((str(point.id), item))
        current = await repository.active_runs(settings)
        if current.get(primary.index_run_id) != identity:
            return replace(
                context, enabled=False, reason="insufficient_evidence", text="", sources=(),
            )

        candidates.sort(key=lambda pair: pair[1].chunk_index)
        chosen = []
        if overview:
            # Chapter outline provides breadth; opening substantive paragraphs provide purpose.
            for point_id, item in candidates:
                headings = re.findall(
                    r"CAP[ÍI]TULO\s+[IVXLCDM]+\s*[:.\-–]?\s*[^\n]+", item.text,
                    flags=re.IGNORECASE,
                )
                if headings:
                    cleaned = []
                    for heading in headings:
                        heading = re.split(r"\.{3,}|Artículo\s+\d", heading)[0].strip()
                        if heading and heading not in cleaned:
                            cleaned.append(heading)
                    text = "\n".join(cleaned)
                    if text:
                        chosen.append((point_id, item, text))
            openings = [(pid, item, item.text) for pid, item in candidates
                        if len(item.text) >= 180 and "..." not in item.text
                        and (item.page_start or 999) >= 7]
            # Prefer real contents pages covering several chapters over scattered headings.
            chosen.sort(key=lambda row: -len(re.findall(
                r"CAP[ÍI]TULO", row[2], flags=re.IGNORECASE,
            )))
            if not chosen:
                chosen = openings[:3]
        else:
            pages = {s.page_start for s in context.sources if s.page_start is not None}
            if focused:
                for pid, item in candidates:
                    if re.search(r"\.{3,}", item.text):
                        continue
                    paragraphs = re.split(r"(?=Artículo\s+\d+\.)", item.text)
                    for paragraph in paragraphs:
                        clean = paragraph.strip()
                        if len(clean) >= 100 and any(t in clean.casefold() for t in focused):
                            chosen.append((pid, item, clean))
            else:
                chosen = [(pid, item, item.text) for pid, item in candidates
                          if len(item.text) >= 100 and item.page_start in pages]
            retrieved_texts = {r["text"] for r in records if len(r["text"]) >= 100}
            terms = {word[:6] for word in re.findall(r"\w+", context.query.casefold())
                     if len(word) > 4}
            def rank(row):
                header = row[2][:80].casefold()
                if focused:
                    boost = 1000 if re.match(r"artículo\s+\d+\.", header) and any(
                        term in header for term in focused
                    ) else 0
                    boost += 2000 * sum(t in normalized and t in header
                                        for t in ("leve", "grave"))
                    return (-boost, row[1].chunk_index)
                score = (100 if row[2] in retrieved_texts else 0) + sum(
                    term in row[2].casefold() for term in terms
                )
                return (-score, row[1].chunk_index)

            chosen.sort(key=rank)

        # Keep evidence bounded; never truncate a legal paragraph or fabricate a citation.
        added = []
        by_point = {}
        seen = set()
        seen_articles = set()
        budget = 3500 if overview else 2200
        for point_id, item, text in chosen:
            if text in seen or len(text) > budget:
                continue
            article = re.match(r"Artículo\s+(\d+)\.", text)
            if focused and article:
                if article[1] in seen_articles:
                    continue
                seen_articles.add(article[1])
            seen.add(text)
            budget -= len(text)
            if point_id in by_point:
                by_point[point_id]["text"] += "\n\n" + text
                continue
            source = ContextSource(
                citation_id=f"S{len(added) + 1}", point_id=point_id,
                document_id=item.document_id, document_version_id=item.document_version_id,
                document_name=item.document_name, version=item.version,
                page_start=item.page_start, page_end=item.page_end, section=item.section,
                index_run_id=item.index_run_id,
            )
            record = {"source": asdict(source), "text": text}
            added.append(record)
            by_point[point_id] = record
            if len(added) >= (16 if overview else 6):
                break
        if not added:
            return context
        if not overview and not focused:
            # Retain useful semantic evidence from other documents as well.
            for record in records:
                if len(record["text"].strip()) < 100 or record["text"] in seen:
                    continue
                if len(record["text"]) > budget:
                    continue
                budget -= len(record["text"])
                source = {**record["source"], "citation_id": f"S{len(added) + 1}"}
                added.append({"source": source, "text": record["text"]})
        text = json.dumps({"sources": added}, ensure_ascii=False)
        sources = tuple(ContextSource(**r["source"]) for r in added)
        return replace(context, text=text, sources=sources, character_count=len(text))
