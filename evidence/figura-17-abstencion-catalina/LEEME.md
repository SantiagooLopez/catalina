# Figura 17 · abstención por evidencia insuficiente

Captura directa del chat de Catalina en http://127.0.0.1:5173/, con el backend real de
Debian. Se escribió y envió la pregunta mediante los controles de la interfaz.
No se simularon respuestas, no se interceptaron peticiones y no se modificaron estilos
ni textos. Se utilizó una ventana de 550 × 720 para una captura legible del widget.

Pregunta: ¿Cuál es el menú de almuerzo de la cafetería de la Universidad Católica de
Colombia para el 15 de noviembre de 2026 y cuánto cuesta?

La API devolvió HTTP 200, reason insufficient_evidence, generated false, model null y
citations vacío. La respuesta que muestra la interfaz es:
«No encontré evidencia institucional suficiente para responder esta pregunta con seguridad.»
Esto evidencia la abstención para esta consulta; no certifica que toda consulta fuera
del corpus se comporte igual.

Archivos:
- figura-17-abstencion.png: captura directa del widget.
- aplicacion-completa.png: ventana completa del navegador.
- respuesta-api-original.json: respuesta original de la API.
- texto-interfaz.txt: texto extraído del DOM mostrado.

Figura 17. Respuesta controlada ante evidencia documental insuficiente.
Fuente: elaboración propia a partir del prototipo Catalina (2026).
