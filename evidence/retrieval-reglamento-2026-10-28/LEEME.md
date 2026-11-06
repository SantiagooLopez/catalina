# Evidencia de recuperación documental

Consulta real ejecutada por SSH en catalina-server el 28 de octubre de 2026.
El JSON contiene la pregunta original y el resultado completo de
ManagedRetrievalService.build(RetrievalQuery(query=QUESTION)). No se aplicó un filtro
para forzar el documento, no se redujeron los umbrales y no se modificó el estado ready.

Archivos:
- resultado-original.json: resultado completo preservado sin cambios.
- reporte-recuperacion.html: presentación legible de los datos originales.
- captura-recuperacion.png: captura en Chrome de ese reporte.

La figura muestra S1, primera fuente del contexto, con su texto literal completo.
S2 y S3 se enumeran y sus textos completos están en el JSON. La puntuación mostrada
es assessment.best_score del conjunto de evidencia, no una puntuación atribuida a S1
ni una probabilidad de corrección.

Este reporte corresponde a recuperación y preparación del contexto, no a una respuesta
generada por el modelo ni a una captura de la interfaz del chat.

Para repetir en Debian con la copia temporal del script:

```bash
cd /opt/catalina/services/ingestion
PYTHONPATH=src .venv/bin/python /tmp/capture_retrieval_evidence.py
```

El script original está en la copia local del repositorio:
services/ingestion/scripts/capture_retrieval_evidence.py.
La copia de /tmp puede desaparecer al reiniciar.

Pie de figura sugerido:
Recuperación del Reglamento del Estudiante, versión 406-2026, ante una consulta sobre
el reglamento aplicable. El contexto retorna ready y una mejor puntuación de evidencia
de 0,6980418; la fuente S1 identifica la página 2, sección ACUERDA, y su fragmento literal.
