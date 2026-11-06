# Guion actualizado: Catalina en tres minutos

Usar el enlace público actual, con ambos equipos encendidos. Empezar sin sesión en ventana privada; tener el correo de prueba y su contraseña preparados, sin mostrarlos ni dictarlos.

| Tiempo | Acción y pregunta | Qué explicar |
|---|---|---|
| 0:00–0:12 | Portada y chat pequeño. | «Catalina es un prototipo académico de asistencia universitaria». |
| 0:12–0:32 | **¿Dónde me puedo matricular?** | «El visitante recibe orientación general y los canales oficiales de admisión». |
| 0:32–0:48 | **¿Qué carreras tiene la universidad?** | «También puede conocer la oferta pública de pregrado». Si prefieres mostrar costos, sustituye esta por **¿Cuánto cuesta la matrícula?** y explica la remisión a Registro y Control. |
| 0:48–1:03 | **¿Dónde queda la biblioteca de Sede 4?** | «Las ubicaciones y consultas documentales requieren iniciar sesión». |
| 1:03–1:18 | Ampliar chat e iniciar sesión. | «La sesión habilita documentos, historial y mapa». |
| 1:18–1:43 | **¿Cuándo finalizan las clases del segundo semestre de 2026?** Abrir la fuente. | «El calendario indica el 21 de noviembre para programas de 16 semanas y el 28 de noviembre para los de 17. Se muestra el documento, su versión y la página. Son fechas de fin de clases; las evaluaciones y el cierre académico son distintos». |
| 1:43–2:04 | **¿Dónde queda la biblioteca de Sede 4?** Mostrar marcador y acercar el mapa. | «El asistente identifica la dependencia en el mapa y permite explorar su ubicación». |
| 2:04–2:27 | Volver al chat: **¿Cuál es el menú de almuerzo de la cafetería de la Universidad Católica de Colombia para el 15 de noviembre de 2026 y cuánto cuesta?** | «Cuando no hay evidencia documental suficiente, Catalina se abstiene de afirmar un dato». |
| 2:27–2:47 | Nueva conversación y volver a la anterior desde el historial. | «Las consultas quedan organizadas por usuario y se pueden retomar». |
| 2:47–3:00 | Cambiar tema claro/oscuro y cerrar sesión. | «La interfaz permite elegir el tema; al cerrar sesión se restringen de nuevo las funciones institucionales». |

## Preguntas para copiar

1. ¿Dónde me puedo matricular?
2. ¿Qué carreras tiene la universidad?
3. ¿Cuánto cuesta la matrícula? (alternativa a la 2)
4. ¿Dónde queda la biblioteca de Sede 4?
5. ¿Cuándo finalizan las clases del segundo semestre de 2026?
6. ¿Dónde queda la biblioteca de Sede 4?
7. ¿Cuál es el menú de almuerzo de la cafetería de la Universidad Católica de Colombia para el 15 de noviembre de 2026 y cuánto cuesta?

## Alcance de la demostración

La orientación pública es contenido curado con enlaces a admisiones.ucatolica.edu.co; no usa la recuperación privada ni cotiza precios. La oferta de pregrados se verificó el 4 de noviembre de 2026 en https://admisiones.ucatolica.edu.co/pregrado/.

La respuesta de fin de clases se extrae de la fila «Terminación clases pregrado» del calendario recuperado, versión 046-2025, página 4. No es una fecha fija programada para la pregunta. Si se pregunta sin indicar semestre, solicita aclaración; otro año no reutiliza estas fechas. Registro de la ejecución: respuesta-fechas-real.json.

Las respuestas del chat y del mapa se muestran con una pausa visual mínima elegida entre 6, 7 y 9 segundos, sin repetir consecutivamente la misma opción. Si el backend tarda más, no se puede garantizar un máximo de 9 segundos. Esta pausa es de presentación, no una medición de rendimiento del modelo. No se muestran etiquetas técnicas ni el contador de duración de respuestas completadas; las fuentes se mantienen visibles.

No afirmar que todas estas respuestas las redactó Ollama: el recorrido incluye orientación pública curada, extracción documental, directorio del campus y abstención. La demostración cubre el recorrido del usuario, no la administración ni todas las condiciones de error.


## Preguntas de respaldo probadas — elegir, no añadir todas al video

El guion principal se conserva. Estas preguntas sustituyen una escena si deseas otra toma; hacerlas todas excedería los tres minutos. Las consultas de calendario, trámites y mapa requieren sesión. Mantener la formulación completa ayuda a identificar el semestre, el programa y el servicio solicitado.

### Calendario: fechas con fuente documental

| Pregunta lista para copiar | Resultado comprobado |
|---|---|
| ¿Cuándo es la semana de receso del segundo semestre de 2026? | Del 5 al 10 de octubre de 2026; fuente del calendario. Son fechas pasadas respecto de la grabación de noviembre. |
| ¿Cuándo son las evaluaciones finales de programas de 16 semanas del segundo semestre de 2026? | Del 23 de noviembre al 5 de diciembre de 2026; fuente del calendario. |
| ¿Cuándo son las evaluaciones finales de programas de 17 semanas del segundo semestre de 2026? | Del 30 de noviembre al 5 de diciembre de 2026; fuente del calendario. |
| ¿Cuándo finalizan las clases del segundo semestre de 2026? | 21 de noviembre (16 semanas) y 28 de noviembre (17 semanas); distinta actividad de las evaluaciones finales. |

### Sedes, facultades y orientación de trámites

| Pregunta lista para copiar | Qué mostrar |
|---|---|
| ¿Dónde puedo hacer trámites de Psicología? | Facultad de Psicología, Sede Las Torres, con su marcador. Orienta a confirmar el área y los requisitos concretos con la facultad. |
| ¿Dónde queda la sede El Claustro? | Área 5; Diagonal 46 A # 15 B – 10. |
| ¿Dónde queda la sede Las Torres? | Área 3; Avenida Caracas # 46 – 72. |
| ¿Dónde queda la Facultad de Derecho? | Marcador dentro de Las Torres. |
| ¿Dónde queda el auditorio de Sede 4? | Marcador del auditorio dentro de Sede 4. |
| ¿Dónde queda la biblioteca de Sede 4? | Marcador específico de la biblioteca, evitando la ambigüedad de preguntar solo «biblioteca». |

El mapa es orientativo. Algunos accesos, pisos u oficinas están pendientes de confirmar; no afirmar que todos los trámites se resuelven en la facultad ni que el directorio contiene horarios verificados. La orientación sobre trámites académicos de Psicología no sustituye la atención de servicios psicológicos o una cita clínica.

### Procedimiento documental, paso a paso

**¿Cómo solicito una constancia académica por PAW 2.0?**

La respuesta comprobada reproduce el procedimiento de Registro y Control Académico: ingresar en PAW 2.0 con perfil de estudiantes, elegir la solicitud de certificados y constancias, verificar datos y seleccionar el documento, y pagar el recibo. El pasaje explica el envío por correo con firma digital y el plazo publicado de hasta ocho días hábiles. Abrir la fuente para mostrar la trazabilidad. Confirmar las condiciones vigentes antes de tramitar.

Frase sugerida para narrar: «Catalina puede recuperar un procedimiento completo y conservar la fuente que respalda cada indicación».

### Antes de iniciar sesión

- ¿Dónde me puedo matricular? → Orientación pública y portal de Admisiones.
- ¿Qué carreras tiene la universidad? → Oferta pública de pregrado y enlace oficial.
- ¿Cuánto cuesta la matrícula? → Orientación hacia Registro y Control, sin inventar una cotización.
- ¿Dónde puedo hacer trámites de Psicología? → Solicita iniciar sesión; repetir después de ingresar muestra la diferencia de acceso.

### Pausa visual ya configurada

El chat y las preguntas del mapa conservan la pausa mínima de presentación variable entre **6, 7 y 9 segundos**, sin repetir la misma opción consecutivamente. Se aplica también a las preguntas de respaldo. Si el procesamiento supera ese plazo, se muestra al terminar; no existe un máximo garantizado de nueve segundos. No presentar esta pausa como latencia de Ollama.

### Registro de comprobación y alcance

Las consultas de receso, evaluaciones finales, sedes y orientación de Psicología se probaron con la API real autenticada; el procedimiento de PAW se volvió a comprobar tras ajustar su enrutamiento para evitar una clasificación innecesaria del modelo. Los resultados están en preguntas-respaldo-probadas.json y respaldo-verificacion-final.json, junto a este guion.

Las formulaciones sobre «evaluación del segundo corte» y «cierre del sistema de información» devolvieron evidencia insuficiente en el ensayo. No se recomiendan para demostrar una respuesta de fecha en esta grabación. Que el dato exista en un documento no garantiza que todas las formulaciones lo recuperen; no se eliminaron esos resultados del registro.

La pregunta sobre terminación de clases del primer semestre de 2026 superó el límite de 60 segundos en el ensayo adicional; tampoco se incluye entre las opciones recomendadas. El registro final identifica ese tiempo de espera como error, sin atribuirle una respuesta anterior.
