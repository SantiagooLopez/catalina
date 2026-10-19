"""Answer literal regulatory lookups with verbatim evidence, preserving legal conditions."""

import json
import re
import unicodedata

from catalina_ingestion.domain.generation import GeneratedAnswer, GenerationReason
from catalina_ingestion.domain.rag_context import RagContext


def resolve_excerpt(context: RagContext) -> GeneratedAnswer | None:
    query = "".join(c for c in unicodedata.normalize("NFKD", context.query.casefold())
                    if not unicodedata.combining(c))
    if not context.enabled or not context.sources:
        return None
    if "reglamento" not in context.sources[0].document_name.casefold():
        return None
    if re.search(r"\b(?:explica\w*|interpreta\w*|analiza\w*|compara\w*)\b", query):
        return None
    if not re.search(r"\b(?:que dice|que establece|que derechos|cuales son los derechos)\b", query):
        return None
    terms = [term for term in ("derech", "deber", "falta", "sancion") if term in query]
    if not terms:
        return None
    records = json.loads(context.text).get("sources", [])
    excerpts = []
    used = set()
    seen = set()
    for record in records:
        source_id = record["source"]["citation_id"]
        if source_id not in {s.citation_id for s in context.sources}:
            return None
        paragraphs = re.split(r"(?=Artículo\s+\d+\.)", record["text"])
        if "derech" in terms:
            expanded = []
            for paragraph in paragraphs:
                if len(paragraph) > 1000 and "\n\n" in paragraph:
                    body = paragraph.split("\n\n", 1)[1]
                    expanded.extend(re.split(
                        r"(?<!\S)(?=\d{1,2}\.\s+[A-ZÁÉÍÓÚÑ])", body,
                    ))
                else:
                    expanded.append(paragraph)
            paragraphs = expanded
        for paragraph in paragraphs:
            text = paragraph.strip()
            if text and text[-1] not in ".!?;:":
                endings = list(re.finditer(r"[.!?](?=\s|$)", text))
                if endings:
                    text = text[:endings[-1].end()].strip()
            if re.search(r"\.{3,}", text):
                continue
            numbered_right = "derech" in terms and re.match(r"\d+\.\s", text)
            if not (35 if numbered_right else 100) <= len(text) <= 1000 or text in seen:
                continue
            if not numbered_right and not any(term in text.casefold() for term in terms):
                continue
            seen.add(text)
            used.add(source_id)
            excerpts.append(f"“{text}” [{source_id}]")
            if len(excerpts) == (5 if "derech" in terms else 3):
                break
        if len(excerpts) == (5 if "derech" in terms else 3):
            break
    if not excerpts:
        return None
    primary = context.sources[0]
    return GeneratedAnswer(
        query=context.query,
        text=(f"Estos son los pasajes pertinentes del {primary.document_name} "
              f"(versión {primary.version}), citados textualmente:\n\n"
              + "\n\n".join(excerpts)),
        generated=False, reason=GenerationReason.DOCUMENT_EXCERPT, model=None,
        citations=tuple(s for s in context.sources if s.citation_id in used),
    )
