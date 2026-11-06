# Figura 16 · captura directa de la aplicación Catalina

La captura se tomó del widget real de http://127.0.0.1:5173/, conectado mediante el proxy
de desarrollo al backend Debian. La pregunta se escribió y envió con los controles
de la interfaz. Se abrió «Consultar 3 fuentes» pulsando su control real.
No hubo interceptores, respuestas simuladas, cambios de CSS ni sustitución de texto.
Se usó una ventana estrecha de 550 × 1100 para que la vista responsive muestre
pregunta, respuesta y fuentes en una sola captura del widget.

La primera llamada devolvió HTTP 200, reason generated y tres fuentes; su respuesta
original está en respuesta-primera-ejecucion.json. La captura final se tomó al repetir
la consulta, que devolvió HTTP 200, reason cached, también con tres fuentes.
Por eso la propia interfaz dice «Respuesta de Ollama reutilizada».

Archivos:
- figura-16-respuesta.png: captura directa del widget con las fuentes desplegadas.
- aplicacion-completa.png: captura completa de la ventana del navegador.
- respuesta-api-original.json: respuesta recibida al realizar la captura final.
- respuesta-primera-ejecucion.json: respuesta inicial generada por Ollama.
- texto-interfaz.txt: texto extraído del DOM de la misma interfaz.

La respuesta se conserva tal como la produjo el sistema, incluidos sus posibles errores.
Mostrar fuentes no constituye por sí solo una validación de cada afirmación generada.

Pie sugerido:
Figura 16. Respuesta de Catalina con referencias al Reglamento del Estudiante,
versión 406-2026, y fuentes desplegadas con identificación de documento, página y sección.
