# Grounded RAG Challenge · 28 de octubre de 2026

Se ejecutó sin modificar el script ni sus umbrales:

```bash
cd /opt/catalina/services/ingestion
.venv/bin/python -u scripts/evaluate_grounded_rag_challenge.py
```

El script evaluó sus 20 preguntas originales contra 6 documentos del corpus activo.
Resultado: TP=10, TN=10, FP=0, FN=0. Las seis métricas de exactitud/precisión impresas
resultaron 1,000 y contamination_count=0 para este conjunto de casos.
La latencia media exacta del JSON fue 178,51785 ms (178,518 ms en la salida redondeada).

ALCANCE DE LA LATENCIA: el cronómetro del script mide ManagedRetrievalService.build(),
que realiza recuperación y validación del contexto. No incluye generación de una
respuesta textual por llama3.2:3b ni el recorrido completo del chat en el navegador.
end_to_end_accuracy es el nombre definido por este evaluador para su criterio compuesto
de habilitación/abstención, fuente esperada, primer resultado y ausencia de contaminación;
no representa una evaluación de la calidad de texto generado por Ollama.

Archivos:
- salida-completa.txt: salida original de la ejecución por SSH.
- resultado-original.json: JSON íntegro producido por el script en Debian.
- resumen-salida.txt: extracto de las líneas de cantidad de casos y resumen final;
  se omiten el detalle por pregunta y la ruta larga del JSON, sin alterar métricas.
- captura-grounded-rag-challenge.png: captura en navegador del extracto de texto anterior.

La captura es del registro guardado de ejecución, no de una ventana de terminal.
Los resultados describen únicamente este dataset de 20 preguntas; no deben interpretarse
como garantía de rendimiento perfecto para cualquier consulta o corpus.

Pie sugerido:
Resultados del evaluador Grounded RAG Challenge sobre 20 consultas del corpus:
métricas de recuperación y validación del contexto, y latencia media observada.
Fuente: elaboración propia a partir del prototipo Catalina (2026).
