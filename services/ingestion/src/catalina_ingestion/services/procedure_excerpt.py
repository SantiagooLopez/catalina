"""Expose a complete retrieved certificate procedure verbatim, preserving its scope."""
import json
import re
import unicodedata
from catalina_ingestion.domain.generation import GeneratedAnswer, GenerationReason
from catalina_ingestion.domain.rag_context import RagContext


def resolve_certificate_procedure(context: RagContext) -> GeneratedAnswer | None:
    query = ''.join(c for c in unicodedata.normalize('NFKD', context.query.casefold())
                    if not unicodedata.combining(c))
    if not context.enabled or not re.search(r'certificad|constancia', query):
        return None
    if not re.search(r'como|pasos|procedimiento|cuanto.*(?:tarda|demora)|plazo', query):
        return None
    for record in json.loads(context.text).get('sources', []):
        source = next((s for s in context.sources if s.citation_id == record['source']['citation_id']), None)
        text = record['text'].strip()
        if source is None or source.document_name != 'Registro y Control Académico':
            continue
        if not text.startswith('Procedimiento:') or not all(f'{i}.' in text for i in range(1, 5)):
            continue
        if 'PAW 2.0' not in text or len(text) > 1800:
            continue
        return GeneratedAnswer(query=context.query,
            text=(f'El documento {source.document_name} describe el procedimiento para '
                  f'certificados y constancias académicas:\n\n{text} [{source.citation_id}]\n\n'
                  'Confirma las condiciones vigentes con la dependencia antes de realizar el trámite.'),
            generated=False, reason=GenerationReason.DOCUMENT_EXCERPT, model=None, citations=(source,))
    return None
