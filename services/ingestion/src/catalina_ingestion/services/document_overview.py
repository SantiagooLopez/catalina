"""An extractive document overview: actual chapter titles, not a model-invented summary."""

import json
import re

from catalina_ingestion.domain.generation import GeneratedAnswer, GenerationReason
from catalina_ingestion.domain.rag_context import RagContext
from catalina_ingestion.services.evidence_expansion import is_overview


def resolve_overview(context: RagContext) -> GeneratedAnswer | None:
    if not context.enabled or not is_overview(context.query):
        return None
    records = json.loads(context.text).get("sources", [])
    topics = {}
    seen = set()
    used = set()
    for record in records:
        citation = record["source"]["citation_id"]
        if citation not in {s.citation_id for s in context.sources}:
            return None
        for number, title in re.findall(
            r"CAP[ÍI]TULO\s+([IVXLCDM]+)\s*[:.\-–]?\s*([^\n]+)",
            record["text"], flags=re.IGNORECASE,
        ):
            title = re.split(r"\.{3,}|Artículo\s+\d", title)[0].strip()
            if not re.search(r"[a-záéíóúñ]{3}", title, re.IGNORECASE):
                continue
            seen.add(title.casefold())
            used.add(citation)
            values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
            digits = [values[c] for c in number.upper()]
            order = sum(-v if i + 1 < len(digits) and v < digits[i + 1] else v
                        for i, v in enumerate(digits))
            rendered = f"• {title.capitalize()}. [{citation}]"
            if order not in topics or len(rendered) > len(topics[order]):
                topics[order] = rendered
    if len(topics) < 4:
        return None
    displayed = sorted(topics.items())[:12]
    used = {match for _, text in displayed for match in re.findall(r"\[(S\d+)\]", text)}
    primary = context.sources[0]
    text = (
        f"El {primary.document_name} (versión {primary.version}) organiza la información "
        "del estudiante. Entre los temas de sus capítulos se encuentran:\n\n"
        + "\n".join(text for _, text in displayed)
        + "\n\nEsta es una visión de su estructura. Los requisitos, derechos o sanciones "
        "concretos deben explicarse a partir de sus artículos, no solo de sus títulos."
    )
    return GeneratedAnswer(
        query=context.query, text=text, generated=False,
        reason=GenerationReason.DOCUMENT_OVERVIEW, model=None,
        citations=tuple(s for s in context.sources if s.citation_id in used),
    )
