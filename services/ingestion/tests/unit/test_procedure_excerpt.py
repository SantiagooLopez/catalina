import json
from dataclasses import asdict, replace
from test_prompt_builder import make_context
from catalina_ingestion.services.procedure_excerpt import resolve_certificate_procedure


def test_only_complete_retrieved_certificate_procedure_is_extracted():
    base = make_context()
    source = replace(base.sources[0], document_name='Registro y Control Académico')
    passage = 'Procedimiento:\n1. Entrar en PAW 2.0.\n2. Elegir solicitud.\n3. Verificar datos.\n4. Pagar recibo.'
    context = replace(base, query='¿Cómo solicito una constancia académica?', sources=(source,),
                      text=json.dumps({'sources':[{'source':asdict(source),'text':passage}]}))
    result = resolve_certificate_procedure(context)
    assert passage in result.text and result.citations == (source,)
    assert resolve_certificate_procedure(replace(context, enabled=False)) is None
    assert resolve_certificate_procedure(replace(context, query='¿Cómo solicito una beca?')) is None
    assert resolve_certificate_procedure(replace(context, text='{"sources":[]}')) is None
