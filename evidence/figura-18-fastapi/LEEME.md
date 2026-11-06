# Figura 18 · documentación FastAPI / Swagger

Captura directa de la documentación servida por el backend real de Catalina:
https://192.168.20.140/docs#/answers/answer_api_v1_answers_post

Se expandió POST /api/v1/answers y se seleccionó la pestaña Schema en el cuerpo de
petición y la respuesta HTTP 200. No se modificó el DOM ni el CSS, no se sustituyeron
valores y no se ejecutó una operación Try it out. Los ejemplos y esquemas son la
documentación generada por FastAPI; no representan una respuesta de una prueba ejecutada.

El contrato de petición requiere conversation_id entero mayor que cero y query de
1 a 1000 caracteres. El contrato de respuesta documenta identificadores de conversación
y mensaje, pregunta, respuesta, origen de generación, modelo, citas, estadísticas y
ubicaciones. Se muestran además los contratos documentados para HTTP 200 y 422.
El candado del endpoint corresponde a la seguridad HTTPBearer definida en OpenAPI.

Archivos:
- figura-18-fastapi.png: captura directa del endpoint desplegado.
- swagger-contexto.png: captura de la ventana del navegador.
- openapi-original.json: esquema OpenAPI descargado del mismo servidor.
- texto-swagger.txt: texto extraído del endpoint mostrado.

Figura 18. Integración del servicio de consulta mediante FastAPI.
Fuente: elaboración propia a partir del prototipo Catalina (2026).
