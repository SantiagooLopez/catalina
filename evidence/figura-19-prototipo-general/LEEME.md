# Figura 19 · vista general del prototipo

Captura directa de la ventana del navegador en http://127.0.0.1:5173/ a 1600 × 1000.
Muestra el portal de Catalina y el widget abierto con pregunta, respuesta y fuente.
La consulta se escribió y envió desde los controles reales de la aplicación, conectada
al backend Debian. No se modificaron estilos, respuestas ni elementos de la interfaz.

Pregunta: ¿Qué acuerdo modificó el calendario académico de pregrado de 2026?
La API devolvió HTTP 200 y reason document_identifier_resolved: la respuesta toma el
identificador 050-2026 de la fuente principal. Es una resolución documental directa,
no una generación de Ollama; así se identifica en la interfaz.
La fuente S1 corresponde a Modificación del Calendario Académico de Pregrado 2026,
versión 050-2026, página 1. Se abrió el control Consultar 1 fuente antes de capturar.

Archivos:
- figura-19-prototipo-general.png: captura general de la aplicación real.
- detalle-chat.png: captura adicional del widget.
- respuesta-api-original.json: respuesta original de la API.
- texto-interfaz.txt: texto del DOM mostrado en el widget.

Figura 19. Vista general del prototipo Catalina en funcionamiento, con consulta,
respuesta y fuente documental desplegada.
Fuente: elaboración propia a partir del prototipo Catalina (2026).
