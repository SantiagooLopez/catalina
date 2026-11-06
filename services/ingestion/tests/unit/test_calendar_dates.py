import json
from dataclasses import asdict, replace
from test_prompt_builder import make_context
from catalina_ingestion.services.calendar_dates import resolve_class_end
from catalina_ingestion.services.calendar_dates import resolve_calendar_event


def calendar_context(query='¿Cuándo finalizan las clases del segundo semestre de 2026?'):
    base = make_context()
    source = replace(base.sources[0], document_name='Calendario Académico de Pregrado 2026', version='046-2025')
    row = ('Terminación clases pregrado 15 16 semanas: 30 mayo de 2026 '
           '16 semanas: 21 noviembre de 2026 17 semanas: 06 junio de 2026 '
           '17 semanas: 28 noviembre de 2026 PROCESOS DE DEVOLUCIONES')
    return replace(base, query=query, sources=(source,), text=json.dumps({
        'sources': [{'source': asdict(source), 'text': row}]}))


def test_extracts_second_semester_end_dates_and_cites_retrieved_source():
    result = resolve_class_end(calendar_context())
    assert '21 noviembre de 2026' in result.text
    assert '28 noviembre de 2026' in result.text
    assert '30 mayo' not in result.text
    assert len(result.citations) == 1
    assert not result.generated


def test_first_semester_uses_other_columns():
    result = resolve_class_end(calendar_context('¿Cuándo terminan las clases del primer semestre de 2026?'))
    assert '30 mayo de 2026' in result.text and '06 junio de 2026' in result.text
    assert '21 noviembre' not in result.text


def test_missing_or_malformed_evidence_never_invents_dates():
    assert resolve_class_end(replace(calendar_context(), text='{"sources":[]}')) is None
    assert resolve_class_end(calendar_context('¿Cuándo terminan clases del segundo semestre de 2027?')) is None
    assert resolve_class_end(replace(calendar_context(), enabled=False)) is None


def test_unspecified_semester_requests_clarification():
    result = resolve_class_end(calendar_context('¿Cuándo finalizan las clases?'))
    assert 'primer o al segundo' in result.text
    assert not result.citations


def test_calendar_row_uses_second_semester_dates_not_first_columns():
    base = calendar_context('¿Cuándo son las evaluaciones finales del segundo semestre de 2026?')
    record = json.loads(base.text)['sources'][0]
    record['text'] = ('47 Evaluación final – 3er. Corte – programas de 16 semanas '
                      '01 junio de 2026 13 junio de 2026 23 noviembre de 2026 05 diciembre de 2026 '
                      '48 Evaluación final – 3er. Corte – programas de 17 semanas')
    result = resolve_calendar_event(replace(base, text=json.dumps({'sources': [record]})))
    assert '23 noviembre' in result.text and '05 diciembre' in result.text
    assert '01 junio' not in result.text
    record['text'] = record['text'].replace('05 diciembre de 2026', '')
    assert resolve_calendar_event(replace(base, text=json.dumps({'sources': [record]}))) is None
