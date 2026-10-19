# Evaluación de latencia y fidelidad — 18 de octubre de 2026

Mismo servidor y modelos: llama3.2:3b y embeddinggemma, sin API externa ni entrenamiento.
El servidor tiene un i5-7200U (2 núcleos físicos, 4 hilos), 11 GiB de RAM e inferencia en CPU.

## Resultados observados

| Pregunta | Base | Optimizada | Método de la respuesta optimizada |
|---|---:|---:|---|
| Hola | 0.00 s | 0.00 s | conversational |
| ¿Cuánto es 17 por 6? | 11.53 s | 2.15 s | general_chat |
| Dime de que trata el reglamento estudiantil | 18.85 s | 0.12 s | document_overview |
| ¿Qué dice el reglamento estudiantil sobre las faltas disciplinarias? | 123.89 s | 0.14 s | document_excerpt |
| ¿Y sobre los derechos de los estudiantes? | 85.73 s | 5.12 s | document_excerpt |
| ¿Cuánto cuesta la matrícula en el año 2099? | 11.59 s | 0.11 s | insufficient_evidence |
| Ahora dame tres consejos generales para estudiar mejor | 70.94 s | 11.56 s | general_chat |

Los modos document_overview y document_excerpt extraen evidencia, **no son generaciones
aceleradas del modelo**. El primero organiza capítulos del índice; el segundo cita pasajes.
general_chat sí utiliza Ollama. insufficient_evidence rechaza una pregunta sin respaldo.
Los saludos sencillos ya eran respuestas directas antes del cambio.

## Comparación separada con generación

Al forzar DOCUMENT_RESPONSE_MODE=generated, la misma pregunta de visión del reglamento
tardó 100.20 s con una respuesta redactada por Ollama. Su repetición
tardó 0.17 s con reason=cached, después de volver a consultar la
evidencia vigente. Ese tiempo de caché tampoco representa la velocidad de inferencia.

La generación documental abierta sigue siendo un límite del equipo actual. No se afirma
que todas las preguntas ni todas las condiciones respondan en menos de un segundo.

## Calidad y cambios

- La búsqueda original devolvía títulos aislados y un fragmento del índice para una petición
  de resumen. Ahora se recupera la estructura de la versión activa, con páginas y citas.
- Se observó una paráfrasis generada que invertía una condición sobre faltas leves. Las
  consultas literales normativas usan pasajes textuales y conservan negaciones y condiciones.
- El corpus contiene encabezados repetidos y listas cortadas. Se prefieren artículos completos,
  se descartan índices en consultas específicas y se evitan duplicados del mismo artículo.
- Los temas generales autónomos no reenvían largos pasajes legales anteriores. Las preguntas
  personales y los seguimientos conservan contexto; el límite por defecto es 4000 caracteres.
- Se omite la clasificación con el modelo en casos claros. Los seguimientos ambiguos todavía
  se reformulan con Ollama y consultan evidencia nueva.
- Cada respuesta nueva indica su método en la interfaz, además de su tiempo observado.

## Reproducibilidad y límites

Desde services/ingestion, con los servicios locales activos:

```bash
.venv/bin/python scripts/benchmark_chat.py --suite --repeat --document-mode extractive
.venv/bin/python scripts/benchmark_chat.py --repeat --document-mode generated
```

El JSON adjunto conserva respuestas y métricas por etapa. Las pruebas usan preguntas e
historial sintéticos y no guardan usuarios ni conversaciones. Los resultados son una sola
pasada secuencial; incluyen efectos de caché de prompts/modelos, sin estimación estadística
de p95, carga simultánea ni arranque en frío. Los milisegundos son del backend y no incluyen
todo el recorrido del navegador. Cambiar a extracción cambia el método y el formato, por lo
que su reducción de latencia no puede atribuirse a una mejora de inferencia de Ollama.

Las citas válidas identifican fuentes permitidas; no prueban por sí solas que una paráfrasis
generada sea fiel. Los pasajes textuales son una selección, no el artículo completo. Para
las explicaciones generadas sigue siendo necesaria la evaluación de fidelidad documental.
