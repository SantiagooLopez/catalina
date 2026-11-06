# Anexo X. Matriz de evaluación técnica del sistema RAG

**Sistema:** Catalina, prototipo académico de asistencia universitaria.
**Fecha de la ejecución evaluada:** 28 de octubre de 2026, 23:28:06 UTC (18:28:06, hora de Colombia).
**Fecha de elaboración del anexo:** 4 de noviembre de 2026.
**Fuente:** elaboración propia a partir de la ejecución del script `scripts/evaluate_grounded_rag_challenge.py` y su archivo de resultados original.

## 1. Objetivo y alcance

Evaluar si el subsistema de recuperación de Catalina habilita un contexto documental cuando existe evidencia en el corpus controlado, selecciona el documento y la versión esperados y deshabilita el contexto ante preguntas no cubiertas. Se examinan además la trazabilidad de las fuentes recuperadas, la presencia de fuentes ajenas al manifiesto de evaluación y la latencia del proceso de recuperación.

La unidad de evaluación es una consulta procesada por ManagedRetrievalService.build(). El conjunto comprende 20 preguntas predefinidas: 10 positivas y 10 negativas difíciles. Se ejecutaron secuencialmente en una corrida registrada. No se estableció un umbral de aceptación experimental de latencia en el script.

Esta prueba no ejecuta la generación de la respuesta final del modelo de lenguaje. Un resultado ready significa que el contexto fue habilitado para su uso posterior; no constituye por sí mismo una respuesta correcta redactada por el agente. Las preguntas negativas se interpretan respecto del corpus evaluado: que un dato no esté cubierto no demuestra que no exista en la universidad o en otras fuentes.

## 2. Entorno y configuración de la evaluación

| Elemento | Configuración / evidencia |
|---|---|
| Servidor | Debian, proyecto /opt/catalina/services/ingestion |
| Persistencia relacional | PostgreSQL; el script comprueba documentos activos y versiones activas contra el manifiesto |
| Recuperación vectorial | Qdrant, colección documentos_universidad |
| Modelo de embeddings | embeddinggemma:latest; 768 dimensiones, comprobadas en la evidencia de indexación complementaria |
| Modelo conversacional del prototipo | llama3.2:3b mediante Ollama; su generación final no forma parte de esta corrida |
| Corpus controlado | 6 documentos identificados por código y versión |
| Casos | 20: 10 positivos y 10 negativos |
| top_k | 5 |
| candidate_k | 20 |
| query_score_threshold | 0.5 |
| minimum_chunk_score | 0.5 |
| minimum_best_score | 0.54 |
| grounding_guard | true |
| Instrumentación | perf_counter(), alrededor de service.build(query); resultado expresado en milisegundos |
| Datos de entrada | evaluation/corpus/manifest.json y evaluation/datasets/challenge_questions.jsonl |
| Resultado preservado | grounded_rag_challenge_20261028T232806Z.json; copia local resultado-original.json |

No se dispone en ese JSON de un inventario de CPU/GPU, RAM, versiones exactas de todos los componentes ni del hash Git de la ejecución. Estos datos deben registrarse en una nueva corrida si se requiere reproducibilidad completa; no deben inferirse del rendimiento.

## 3. Corpus de referencia

| ID | Documento | Código | Versión |
|---|---|---|---|
| DOC001 | Reglamento del Estudiante | reglamento-estudiantil | 406-2026 |
| DOC002 | Calendario Académico de Pregrado 2026 | calendario-academico-pregrado-2026 | 046-2025 |
| DOC003 | Marco Institucional de Bienestar Universitario | bienestar-universitario | 340-2022 |
| DOC004 | Registro y Control Académico | registro-control-academico | snapshot-2026 |
| DOC005 | Contactos y ubicaciones | contactos-ubicaciones | snapshot-2026 |
| DOC006 | Modificación del Calendario Académico de Pregrado 2026 | modificacion-calendario-pregrado-2026 | 050-2026 |

Las versiones snapshot-2026 identifican instantáneas de páginas incluidas en el corpus; no deben presentarse como números de acuerdo. El manifiesto contiene seis documentos, pero los casos positivos de este conjunto esperan fuentes de cinco de ellos; DOC003 no es el documento esperado principal de ningún caso positivo. Por tanto, el resultado no demuestra cobertura exhaustiva de los seis documentos.

## 4. Criterios operacionales y métricas

| Criterio | Regla aplicada | Denominador / alcance |
|---|---|---|
| Habilitación correcta | should_answer=true y enabled=true → TP; should_answer=false y enabled=false → TN | 20 consultas |
| Omisión | should_answer=true y enabled=false → FN | Casos positivos |
| Habilitación indebida | should_answer=false y enabled=true → FP | Casos negativos |
| Coincidencia de fuente | Al menos una fuente coincide con expected_document_code y expected_version | 10 positivos; no equivale a relevancia de todos los fragmentos |
| Coincidencia top-1 | La primera fuente coincide con documento y versión esperados | 10 positivos |
| Contaminación de corpus | Alguna fuente tiene document_id no presente en el mapa construido desde el manifiesto | 20 consultas; no mide contaminación del entrenamiento ni instrucciones maliciosas |
| Aprobación compuesta positiva | enabled y source_match y top1_match y ausencia de contaminación | 10 positivos |
| Aprobación compuesta negativa | Contexto deshabilitado | 10 negativos |
| Trazabilidad | Inspección de los metadatos conservados por fuente: cita, fragmento, documento, versión, página y sección | Comprobación documental complementaria, no métrica semántica de la respuesta final |
| Latencia | Tiempo transcurrido de service.build(query) | Excluye generación final, transporte al navegador y pausas de presentación |

El puntaje best_score es el valor registrado por el evaluador de evidencia. No es una probabilidad de veracidad ni un porcentaje de confianza calibrado. El código de estado reason explica la decisión del pipeline y debe interpretarse junto a enabled y al resultado esperado.

## 5. Matriz de casos: entrada y expectativa

| ID | Pregunta | Tipo del conjunto | ¿Debe habilitar contexto? | Documento / versión esperados |
|---|---|---|---|---|
| H001 | ¿Qué reglamento rige actualmente a los estudiantes de la Universidad Católica de Colombia? | paraphrase | Sí | reglamento-estudiantil / 406-2026 |
| H002 | ¿Qué establece el reglamento sobre la inscripción a un programa académico? | paraphrase | Sí | reglamento-estudiantil / 406-2026 |
| H003 | ¿Qué indica el reglamento sobre la cancelación total o parcial de la carga académica? | paraphrase | Sí | reglamento-estudiantil / 406-2026 |
| H004 | ¿En qué parte del reglamento se encuentran los derechos y deberes de los estudiantes? | paraphrase | Sí | reglamento-estudiantil / 406-2026 |
| H005 | ¿Cuál es la dirección y el correo de Bienestar Universitario? | location | Sí | contactos-ubicaciones / snapshot-2026 |
| H006 | ¿Qué áreas y servicios tiene Bienestar Universitario? | paraphrase | Sí | contactos-ubicaciones / snapshot-2026 |
| H007 | ¿Cómo solicito una constancia académica por PAW 2.0? | procedure | Sí | registro-control-academico / snapshot-2026 |
| H008 | ¿Cuánto puede tardar la entrega de un certificado académico solicitado en línea? | direct | Sí | registro-control-academico / snapshot-2026 |
| H009 | ¿Qué documento contiene el calendario académico de pregrado para el año 2026? | paraphrase | Sí | calendario-academico-pregrado-2026 / 046-2025 |
| H010 | ¿Qué acuerdo modificó el calendario académico de pregrado de 2026? | direct | Sí | modificacion-calendario-pregrado-2026 / 050-2026 |
| H011 | ¿Cuáles son las fechas del calendario académico de pregrado para 2027? | hard_negative | No | Sin fuente suficiente esperada |
| H012 | ¿Dónde queda la sede de la Universidad Católica de Colombia en Medellín? | hard_negative | No | Sin fuente suficiente esperada |
| H013 | ¿Bienestar Universitario ofrece servicio de odontología a los estudiantes? | hard_negative | No | Sin fuente suficiente esperada |
| H014 | ¿Qué establece el reglamento de profesores de la Universidad Católica de Colombia? | hard_negative | No | Sin fuente suficiente esperada |
| H015 | ¿Cuánto cuesta la matrícula de Ingeniería Civil para 2026? | hard_negative | No | Sin fuente suficiente esperada |
| H016 | ¿Cómo puedo restablecer mi contraseña de PAW 2.0? | hard_negative | No | Sin fuente suficiente esperada |
| H017 | ¿Cuándo serán las ceremonias de grado del año 2027? | hard_negative | No | Sin fuente suficiente esperada |
| H018 | ¿Cuántos cupos de parqueadero para estudiantes tiene la sede El Claustro? | hard_negative | No | Sin fuente suficiente esperada |
| H019 | ¿Cuál es la dirección de la sede de la Universidad Católica de Colombia en Cali? | hard_negative | No | Sin fuente suficiente esperada |
| H020 | ¿Qué beca institucional garantiza el pago del cien por ciento de la matrícula a todos los estudiantes? | hard_negative | No | Sin fuente suficiente esperada |

## 6. Matriz de resultados observados

| ID | Contexto | Motivo registrado | Mejor puntaje | Clasificación | Fuente correcta | Top-1 correcto | Contaminación | Latencia (ms) | Criterio compuesto |
|---|---|---|---|---|---|---|---|---|
| H001 | Habilitado | ready | 0.6980418 | TP | Sí | Sí | No | 1423,700 | Cumple |
| H002 | Habilitado | ready | 0.63949 | TP | Sí | Sí | No | 118,186 | Cumple |
| H003 | Habilitado | ready | 0.7377877 | TP | Sí | Sí | No | 122,446 | Cumple |
| H004 | Habilitado | ready | 0.69807506 | TP | Sí | Sí | No | 128,196 | Cumple |
| H005 | Habilitado | ready | 0.73030865 | TP | Sí | Sí | No | 107,090 | Cumple |
| H006 | Habilitado | ready | 0.745427 | TP | Sí | Sí | No | 102,657 | Cumple |
| H007 | Habilitado | ready | 0.7801024 | TP | Sí | Sí | No | 110,826 | Cumple |
| H008 | Habilitado | ready | 0.5438516 | TP | Sí | Sí | No | 101,039 | Cumple |
| H009 | Habilitado | ready | 0.85349923 | TP | Sí | Sí | No | 124,769 | Cumple |
| H010 | Habilitado | ready | 0.78103775 | TP | Sí | Sí | No | 137,960 | Cumple |
| H011 | Deshabilitado | unsupported_grounding | 0.6205307 | TN | N/A | N/A | No | 110,802 | Cumple |
| H012 | Deshabilitado | unsupported_grounding | 0.6967979 | TN | N/A | N/A | No | 105,249 | Cumple |
| H013 | Deshabilitado | unsupported_grounding | 0.6045988 | TN | N/A | N/A | No | 108,492 | Cumple |
| H014 | Deshabilitado | unsupported_grounding | 0.62391275 | TN | N/A | N/A | No | 106,975 | Cumple |
| H015 | Deshabilitado | insufficient_evidence | 0.5139152 | TN | N/A | N/A | No | 100,635 | Cumple |
| H016 | Deshabilitado | insufficient_evidence | N/D | TN | N/A | N/A | No | 97,703 | Cumple |
| H017 | Deshabilitado | unsupported_grounding | 0.57904094 | TN | N/A | N/A | No | 111,524 | Cumple |
| H018 | Deshabilitado | insufficient_evidence | N/D | TN | N/A | N/A | No | 104,199 | Cumple |
| H019 | Deshabilitado | unsupported_grounding | 0.70608896 | TN | N/A | N/A | No | 116,409 | Cumple |
| H020 | Deshabilitado | insufficient_evidence | N/D | TN | N/A | N/A | No | 131,500 | Cumple |

N/A indica que no se exige una fuente correcta para una consulta negativa. El archivo original almacena source_match y top1_match como false en estos casos; no se contabilizan como errores de recuperación de los casos positivos.

## 7. Matriz de confusión

| Condición esperada | Contexto habilitado | Contexto deshabilitado | Total |
|---|---:|---:|---:|
| Evidencia suficiente esperada | TP = 10 | FN = 0 | 10 |
| Evidencia insuficiente esperada | FP = 0 | TN = 10 | 10 |
| Total | 10 | 10 | 20 |

## 8. Indicadores consolidados

| Indicador | Fórmula / cálculo | Resultado |
|---|---|---:|
| Precisión de habilitación | TP / (TP + FP) = 10/10 | 100 % |
| Sensibilidad (recall de habilitación) | TP / (TP + FN) = 10/10 | 100 % |
| Exactitud de clasificación | (TP + TN) / N = 20/20 | 100 % |
| F1 de habilitación | 2 × precisión × recall / (precisión + recall) | 100 % |
| Especificidad | TN / (TN + FP) = 10/10 | 100 % |
| Acierto de fuente documental | Positivos con fuente y versión esperadas / positivos = 10/10 | 100 % |
| Acierto top-1 documental | Positivos con primera fuente y versión esperadas / positivos = 10/10 | 100 % |
| Cumplimiento compuesto | Casos aprobados / total = 20/20 | 100 % |
| Consultas con contaminación de corpus | Consultas con fuente ajena al manifiesto / total = 0/20 | 0 % |
| Latencia media | Suma de latencias / 20 | 178,518 ms |
| Latencia mediana | Media de posiciones 10 y 11 ordenadas | 110,814 ms |
| Latencia mínima | Menor valor observado | 97,703 ms |
| Latencia máxima | Mayor valor observado | 1423,700 ms |

F1, especificidad, mediana, mínimo y máximo se calcularon para este anexo a partir de los registros originales; no son campos adicionales emitidos por el script. El indicador end_to_end_accuracy del JSON se denomina aquí cumplimiento compuesto para evitar confundirlo con una evaluación de generación extremo a extremo.

Estos indicadores no son precision@k o recall@k de fragmentos: el conjunto no contiene un juicio exhaustivo de relevancia por fragmento ni todas las unidades relevantes. Tampoco son medidas de fidelidad o factualidad de respuestas generadas.

## 9. Trazabilidad y ejemplos representativos

### Caso H001

- Consulta: ¿Qué reglamento rige actualmente a los estudiantes de la Universidad Católica de Colombia?
- Estado: ready; contexto habilitado: sí.
- Documento principal: Reglamento del Estudiante.
- Versión: 406-2026.
- Cita: S1; página: 2; sección: ACUERDA:.
- document_id: 6; document_version_id: 6.
- point_id: 38401e91-d653-5452-96ac-5d76d4b10bc6.
- Mejor puntaje: 0.6980418; latencia: 1423,700 ms.

### Caso H010

- Consulta: ¿Qué acuerdo modificó el calendario académico de pregrado de 2026?
- Estado: ready; contexto habilitado: sí.
- Documento principal: Modificación del Calendario Académico de Pregrado 2026.
- Versión: 050-2026.
- Cita: S1; página: 1; sección: 1992 y de las establecidas en el artículo 25 de los Estatutos de la Universidad y CONSIDERANDO:.
- document_id: 11; document_version_id: 11.
- point_id: 56e9a33f-3a16-58ce-a091-de387893b140.
- Mejor puntaje: 0.78103775; latencia: 137,960 ms.


En los registros se conservaron 34 apariciones de fuentes; 34 incluyen page_start no nulo. Este conteo corresponde a apariciones por consulta, no necesariamente a fragmentos únicos. El JSON del challenge no incluye index_run_id por fuente: ese vínculo debe consultarse en la evidencia complementaria de recuperación o indexación si se necesita documentarlo.

Distribución de motivos registrados: ready (10); unsupported_grounding (6); insufficient_evidence (4).

## 10. Procedimiento de reproducción

1. Encender Debian y comprobar PostgreSQL, Qdrant y Ollama. Confirmar la configuración de conexión sin publicar credenciales.
2. Verificar que los seis documentos del manifiesto y sus versiones estén activos. Preservar el manifiesto y el conjunto de preguntas usados.
3. Desde /opt/catalina/services/ingestion, ejecutar el comando siguiente con el entorno real del servicio:

```bash
.venv/bin/python scripts/evaluate_grounded_rag_challenge.py
```

4. Guardar stdout y el nuevo JSON producido en evaluation/results/. No sobrescribir la corrida histórica para atribuirle resultados de una versión posterior.
5. Registrar fecha, revisión Git, versiones de software, características del equipo, estado de caché/calentamiento y concurrencia. Repetir corridas si se desea caracterizar estabilidad temporal.
6. Contrastar pregunta por pregunta la habilitación, fuentes, versiones, primer resultado, motivo y latencia. Incorporar fallos observados sin excluirlos del denominador.

## 11. Limitaciones e interpretación

Los 20 casos del conjunto controlado cumplieron el criterio definido por el script. Este resultado acredita el comportamiento observado del subsistema de recuperación en esa corrida, pero no demuestra exactitud universal del sistema RAG ni ausencia de alucinaciones del modelo.

- El conjunto es pequeño, balanceado y predefinido. No representa por sí solo todas las consultas de estudiantes ni una muestra aleatoria de uso real.
- La ejecución es una sola corrida secuencial; no es una prueba de carga o concurrencia. No hay separación documentada entre mediciones en frío y en caliente.
- La latencia de recuperación no puede usarse para afirmar que Ollama redacta una respuesta en 178,518 ms.
- La exactitud de fuentes evalúa documento y versión, no la suficiencia semántica de cada fragmento para redactar una respuesta completa.
- La validación de vigencia se limita a las versiones activas registradas y a las esperadas por el conjunto; no demuestra que se haya auditado toda la normativa posterior.
- La ausencia de contaminación significa que las fuentes pertenecen a los documentos del manifiesto, no que se hayan evaluado ataques de prompt injection.
- La abstención aquí corresponde al bloqueo del contexto. Las capturas de respuestas finales de abstención constituyen evidencia adicional del flujo de aplicación, independiente de esta métrica.
- Las modificaciones de orientación pública, permisos, extracción de fechas y pausas visuales del 4 de noviembre son posteriores a la corrida. No deben atribuirse a esta evaluación histórica sin ejecutarla nuevamente.

Como ampliación futura, se recomienda evaluar respuestas finales con una rúbrica humana de exactitud factual, fidelidad al documento, cobertura de la pregunta, corrección de citas y utilidad; además, incorporar consultas ambiguas, documentos contradictorios o sustituidos, y pruebas de concurrencia. Esas mediciones quedan pendientes y no deben registrarse como aprobadas.

## 12. Texto de cierre sugerido para el anexo

La evaluación técnica del subsistema de recuperación se realizó mediante un conjunto controlado de 20 consultas, compuesto por 10 casos con evidencia esperada y 10 casos negativos. La ejecución registró 10 verdaderos positivos, 10 verdaderos negativos y ningún falso positivo o falso negativo. En los casos positivos, el documento y la versión esperados estuvieron presentes entre las fuentes y ocuparon la primera posición. No se detectaron fuentes ajenas al manifiesto. La latencia media de recuperación fue de 178,518 ms. Los resultados se circunscriben a la corrida y al corpus evaluados y no incluyen la generación de la respuesta final del modelo ni las pausas de presentación de la interfaz.

**Fuente de tablas y resultados:** elaboración propia a partir del prototipo Catalina y del archivo grounded_rag_challenge_20261028T232806Z.json (2026).

## 13. Archivos de respaldo

- resultado-original.json: resultado completo e inalterado de la corrida histórica.
- salida-completa.txt: salida guardada del script.
- manifest.json: manifiesto del corpus usado como referencia.
- challenge_questions.jsonl: preguntas y expectativas.
- evaluate_grounded_rag_challenge.py: copia del evaluador consultado para interpretar las métricas.

El anexo separa los resultados medidos de los cálculos derivados y de las verificaciones futuras propuestas. No incorpora el número de pruebas unitarias como si fueran casos de evaluación RAG: son evidencias diferentes.
