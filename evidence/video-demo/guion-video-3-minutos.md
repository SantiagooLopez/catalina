# Catalina: guion de demostración de tres minutos

Preparado y probado el 4 de noviembre de 2026.

Acceso: https://filled-everything-shipment-sam.trycloudflare.com/

## Antes de grabar

- Mantener Windows, Debian, el frontend y cloudflared encendidos, sin suspensión.
- Usar una ventana privada a 1440 × 1000 aproximadamente, zoom del navegador al 100 %, tema claro.
- Tener las preguntas de abajo en un bloc para copiarlas y pegarlas. No mostrar la contraseña en pantalla ni leerla en voz alta. La cuenta de prueba es rapaez21@ucatolica.edu.co.
- Comenzar en la portada, sin sesión, con el chat cerrado. Activar No molestar en Windows y cerrar pestañas ajenas a la demostración.
- Las consultas de ensayo fueron eliminadas; no se borró ningún historial previo del usuario.

## Guion y acciones

| Tiempo | Acción en pantalla | Narración sugerida |
|---|---|---|
| 0:00–0:15 | Mostrar portada; abrir el chat pequeño. | «Catalina es un prototipo académico de asistencia universitaria. Su portal permite empezar una conversación y acceder a funciones adicionales al iniciar sesión». |
| 0:15–0:30 | Preguntar **¿Qué puedes hacer?** Leer el alcance de la orientación pública. | «Sin sesión, el asistente explica cómo utilizar la página y qué funciones ofrece». |
| 0:30–0:45 | Preguntar **¿Dónde queda la biblioteca de Sede 4?** Mostrar la solicitud de inicio de sesión. | «Las consultas institucionales y las ubicaciones requieren autenticación. Esta restricción también se aplica en la API». |
| 0:45–1:00 | Ampliar el chat. Ingresar con la cuenta de prueba. | «Al iniciar sesión se habilitan el historial, la consulta documental y el mapa interactivo». |
| 1:00–1:25 | Preguntar **¿Qué acuerdo modificó el calendario académico de pregrado de 2026?** Abrir **Consultar fuentes**. | «Esta consulta recupera el identificador 050-2026 desde el documento. La fuente muestra el nombre, la versión y la página. En este caso se extrae información del documento; no se genera una respuesta nueva con Ollama». |
| 1:25–1:50 | Preguntar **¿Dónde queda la biblioteca de Sede 4?** Se abre el mapa. Mostrar el marcador; acercar una vez y pasar el puntero sobre él. | «La ubicación seleccionada corresponde a la biblioteca de Sede 4. El mapa permite identificar la dependencia y consultar su información». |
| 1:50–2:15 | Volver al chat y preguntar **¿Cuál es el menú de almuerzo de la cafetería de la Universidad Católica de Colombia para el 15 de noviembre de 2026 y cuánto cuesta?** | «Cuando no encuentra evidencia suficiente, Catalina se abstiene de dar una respuesta documental. Así evita presentar un dato sin respaldo». |
| 2:15–2:40 | Crear una nueva conversación. Volver a la conversación anterior desde el historial; buscarla por una palabra de su título si es necesario. | «Las conversaciones se conservan por usuario. Puedo iniciar otra consulta y retomar las preguntas anteriores desde el historial». |
| 2:40–3:00 | Alternar modo oscuro y claro. Cerrar sesión. | «La interfaz ofrece temas claro y oscuro. Al cerrar sesión, las funciones institucionales vuelven a requerir autenticación». |

Si el mapa permanece abierto, usar **Volver al chat** antes de enviar la pregunta de abstención. Dejar cada resultado visible unos segundos para que pueda leerse; las respuestas pueden llegar antes de terminar la narración.

## Preguntas listas para copiar

1. ¿Qué puedes hacer?
2. ¿Dónde queda la biblioteca de Sede 4?
3. ¿Qué acuerdo modificó el calendario académico de pregrado de 2026?
4. ¿Dónde queda la biblioteca de Sede 4?
5. ¿Cuál es el menú de almuerzo de la cafetería de la Universidad Católica de Colombia para el 15 de noviembre de 2026 y cuánto cuesta?

Pregunta alternativa si quieres mostrar una respuesta documental más extensa: **Dime de qué trata el reglamento estudiantil**. Devuelve una vista del índice de la versión 406-2026, con citas. Sustituir la consulta del calendario por esta, sin añadirla a las otras si se debe respetar el límite de tres minutos.

## Tiempos y alcance comprobados

En los ensayos autenticados, la consulta del acuerdo tardó 0,21 s; la biblioteca de Sede 4, 0,13 s; la abstención, 0,19 s; la vista del reglamento, 0,17 s. Son tiempos medidos de API en esta red y ejecución; no garantizan el tiempo de otra conexión ni de otras preguntas. Los registros están en preguntas-probadas.json y preguntas-adicionales.json.

No se añadieron esperas artificiales de 5–10 segundos. Para la grabación, dedicar ese tiempo a leer y explicar cada resultado. Las consultas elegidas emplean recuperación, extracción o directorio, y no prueban la generación libre de Ollama ni su latencia. No afirmar en el video que todas las respuestas son generadas por el modelo.

Esta demostración cubre el recorrido conversacional del usuario. No cubre todas las funciones administrativas, la carga/indexación de documentos ni todas las condiciones de error del sistema; esas requieren otra demostración.

## Cambios y verificaciones

- Invitados: saludos y orientación sobre la página; documentos, trámites, temas externos y ubicaciones solicitan iniciar sesión.
- API del catálogo y consultas del campus: exige token válido; sin sesión devuelve 401.
- Frontend: envía el token al mapa, limpia el catálogo en cambios de sesión y muestra sugerencias públicas coherentes.
- Backend: 504 pruebas aprobadas. Frontend: 3 pruebas aprobadas y compilación correcta antes del ajuste final de textos; compilación final comprobada por separado.
- Inicio de sesión y mapa comprobados en navegador real con la cuenta de prueba: 13 marcadores, sin errores de JavaScript. Esta revisión no simuló respuestas de la API.

La restricción aplicada controla las respuestas y el directorio de la API. La portada mantiene una vista previa ilustrativa del plano; no debe describirse el mapa como información confidencial ni como un archivo completamente privado.
