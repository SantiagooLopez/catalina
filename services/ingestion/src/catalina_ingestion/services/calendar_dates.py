"""Extract class end dates from retrieved calendar rows, without fixed date answers."""
import json
import re
import unicodedata

from catalina_ingestion.domain.generation import GeneratedAnswer, GenerationReason
from catalina_ingestion.domain.rag_context import RagContext


def resolve_calendar_event(context: RagContext) -> GeneratedAnswer | None:
    """Read bounded table rows; decline layouts with unexpected date counts."""
    query = ''.join(c for c in unicodedata.normalize('NFKD', context.query.casefold())
                    if not unicodedata.combining(c))
    if not context.enabled or any(y != '2026' for y in re.findall(r'\b20\d{2}\b', query)):
        return None
    first = bool(re.search(r'primer semestre|2026\s*[-/]\s*1', query))
    second = bool(re.search(r'segundo semestre|2026\s*[-/]\s*3', query))
    if first == second:
        return None
    events = [
        (r'receso', 'Semana de receso académica', r'Semana de receso acad[eé]mica.*?\)', r'\b\d+\s+Cancelaciones', 'second_range'),
        (r'evaluacion\w* finales|examen\w* finales|evaluacion final', 'Evaluación final de programas de 16 semanas', r'Evaluaci[oó]n final\s*[–-]\s*3er\. Corte\s*[–-]\s*programas de 16 semanas', r'\b\d+\s+Evaluaci[oó]n final', 'range'),
        (r'segundo corte|2o\.? corte', 'Evaluación de segundo corte', r'Evaluaci[oó]n 2o\. Corte', r'\b\d+\s+Reporte de calificaciones', 'range'),
        (r'cierre.*(?:sistema|informacion)|cierra.*(?:sistema|periodo)', 'Cierre del período en el sistema de información', r'Cierre periodo sistema de informaci[oó]n', r'$', 'single'),
    ]
    for trigger, label, start, end, kind in events:
        if not re.search(trigger, query):
            continue
        # Do not present a 16-week finals row as the 17-week schedule.
        if 'final' in label.casefold() and '17 semanas' in query:
            start = r'Evaluaci[oó]n final\s*[–-]\s*3er\. Corte\s*[–-]\s*programas de 17 semanas'
            end = r'\b\d+\s+Reporte evaluaci[oó]n final'
            label = 'Evaluación final de programas de 17 semanas'
        for record in json.loads(context.text).get('sources', []):
            source = next((s for s in context.sources if s.citation_id == record['source']['citation_id']), None)
            if source is None or 'calendario' not in source.document_name.casefold() or '2026' not in source.document_name:
                continue
            text = ' '.join(record['text'].split())
            row = re.search(start + r'(.*?)' + end, text, re.I)
            if not row:
                continue
            dates = re.findall(r'\b\d{1,2}\s+[a-záéíóú]+\s+de\s+2026\b', row[1], re.I)
            if kind == 'second_range':
                if not second or len(dates) != 2:
                    continue
                detail = f'del {dates[0]} al {dates[1]}'
            elif kind == 'range':
                if len(dates) != 4:
                    continue
                offset = 0 if first else 2
                detail = f'del {dates[offset]} al {dates[offset + 1]}'
            else:
                if len(dates) != 2:
                    continue
                detail = dates[0 if first else 1]
            return GeneratedAnswer(query=context.query,
                text=(f'Según el {source.document_name}, para el {"primer" if first else "segundo"} '
                      f'semestre de 2026:\n\n{label}: {detail}. [{source.citation_id}]\n\n'
                      'Esta fecha corresponde a la actividad indicada; no equivale necesariamente a la terminación de clases.'),
                generated=False, reason=GenerationReason.DOCUMENT_EXCERPT, model=None, citations=(source,))
    return None


def resolve_class_end(context: RagContext) -> GeneratedAnswer | None:
    query = ''.join(c for c in unicodedata.normalize('NFKD', context.query.casefold())
                    if not unicodedata.combining(c))
    if not context.enabled or 'clases' not in query or not re.search(r'finaliz|termin|acaban|fin de', query):
        return None
    if any(year != '2026' for year in re.findall(r'\b20\d{2}\b', query)):
        return None
    first = bool(re.search(r'primer semestre|2026\s*[-/]\s*1', query))
    second = bool(re.search(r'segundo semestre|2026\s*[-/]\s*3', query))
    if first == second:
        return GeneratedAnswer(query=context.query,
            text='¿Te refieres al primer o al segundo semestre de 2026? La terminación de clases también depende de si tu programa es de 16 o 17 semanas.',
            generated=False, reason=GenerationReason.DOCUMENT_EXCERPT, model=None, citations=())
    for record in json.loads(context.text).get('sources', []):
        source = next((s for s in context.sources if s.citation_id == record['source']['citation_id']), None)
        if source is None or 'calendario' not in source.document_name.casefold() or '2026' not in source.document_name:
            continue
        text = ' '.join(record['text'].split())
        row = re.search(r'Terminaci[oó]n clases pregrado(.*?)(?:PROCESOS DE|$)', text, re.I)
        if not row:
            continue
        dates = re.findall(r'(16|17) semanas:\s*(\d{1,2}\s+\w+\s+de\s+2026)', row[1], re.I)
        # Original table: 16 weeks first semester, 16 weeks second semester,
        # then 17 weeks first semester, 17 weeks second semester.
        if [weeks for weeks, _ in dates] != ['16', '16', '17', '17']:
            continue
        offset = 0 if first else 1
        semester = 'primer' if first else 'segundo'
        return GeneratedAnswer(query=context.query,
            text=(f'Según el {source.document_name}, para el {semester} semestre de 2026 '
                  f'las clases de pregrado terminan así:\n\n'
                  f'• Programas de 16 semanas: {dates[offset][1]}.\n'
                  f'• Programas de 17 semanas: {dates[offset + 2][1]}. [{source.citation_id}]\n\n'
                  'Estas fechas corresponden a la terminación de clases; las evaluaciones finales '
                  'y el cierre del período son actividades distintas. Confirma la duración de tu programa.'),
            generated=False, reason=GenerationReason.DOCUMENT_EXCERPT, model=None, citations=(source,))
    return None
