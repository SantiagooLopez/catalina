# Catalina

Asistente universitario con conversación general en Ollama y consultas institucionales
basadas en documentos. El backend está en `services/ingestion` y el frontend React en
`frontend/web`.

## Cómo responde

- Saludos y agradecimientos sencillos se responden directamente.
- Las consultas autónomas claras se enrutan sin llamar al modelo. En casos ambiguos,
  Ollama decide entre conversación general y consulta institucional.
  La decisión usa una salida JSON validada. Si una pregunta está incompleta y no hay
  contexto suficiente, el modo general pide una aclaración.
- La conversación general recibe mensajes recientes del chat y no consulta Qdrant.
- Las preguntas institucionales se reformulan con el contexto necesario y pasan por la
  recuperación de documentos, controles de evidencia y validación de citas existentes.
- Las vistas generales de reglamentos se extraen de los capítulos reales del índice.
  Las consultas literales sobre derechos, deberes o faltas priorizan pasajes textuales,
  con su página y fuente, para preservar las condiciones de la norma.
- `DOCUMENT_RESPONSE_MODE=extractive` permite estas rutas y es el modo predeterminado.
  Con `generated`, las respuestas documentales pasan por Ollama (salvo la resolución
  estructurada de identificadores que ya existía). La interfaz identifica cada método;
  los tiempos de extracción no se presentan como tiempos de generación.
- La búsqueda amplía encabezados insuficientes dentro del mismo documento y versión activa;
  agrupa artículos y evita índices, títulos duplicados y listas incompletas como evidencia principal.
- En las respuestas institucionales, el modelo devuelve texto y una selección estructurada
  de citas permitidas. La API valida los identificadores y los representa en la respuesta.
- Las respuestas anteriores ayudan a entender la conversación; no sustituyen documentos
  como evidencia institucional. Si no hay respaldo documental suficiente, no se recurre
  a generación general para inventar una respuesta.

No se han reentrenado los pesos del modelo. Se utiliza `llama3.2:3b` ya instalado,
con instrucciones, selección de modo y contexto reciente recuperado de PostgreSQL.
La memoria está limitada por defecto a ocho intercambios y 4000 caracteres por chat;
no se comparte entre usuarios o conversaciones y no es memoria permanente del modelo.
El clasificador y el modelo pueden equivocarse: estas reglas reducen errores, pero no
garantizan exactitud absoluta. El modo general no tiene búsqueda web.

Al pasar a una pregunta general autónoma se omite el historial documental irrelevante;
las preguntas personales o de seguimiento conservan contexto. Hay una caché de hasta
64 respuestas generadas institucionales durante diez minutos. Antes de reutilizarla
se consulta de nuevo la evidencia vigente: un cambio en las fuentes invalida la clave.
`reason=cached` no atribuye una nueva generación ni estadísticas del modelo al resultado.

## Desarrollo y verificación

Consulta `frontend/web/README.md` para ejecutar el frontend en Windows. Crea su `.env`
desde `.env.example`; no agregues secretos al repositorio. El proxy de desarrollo
puede consultar el backend de Debian sin instalar las bases de datos en Windows.

En Debian, desde `/opt/catalina/services/ingestion`:

```bash
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python scripts/check_conversation_modes.py
.venv/bin/python scripts/benchmark_chat.py --suite --repeat
```

La segunda comprobación usa Ollama y las bases actuales, con mensajes ficticios,
sin crear usuarios ni persistir conversaciones. Verifica respuestas generales,
memoria reciente, búsqueda institucional y continuidad de una consulta.

Los parámetros `CHAT_HISTORY_TURNS`, `CHAT_HISTORY_CHARACTERS`, `CHAT_MAX_CONCURRENT`
y `CHAT_TIMEOUT_SECONDS` se documentan en `services/ingestion/.env.example`.
Los registros `chat_timing`, `ollama_timing` y `retrieval_completed` permiten separar
espera, carga, procesamiento de contexto y generación sin registrar mensajes personales.
El benchmark usa exclusivamente preguntas e historial sintéticos y no escribe conversaciones.
Consulta `services/ingestion/evaluation/performance/README.md` para las mediciones y límites.

## Despliegue actual

Debian ejecuta `catalina-api.service` en `127.0.0.1:8000`, con Nginx delante,
Ollama local y PostgreSQL/Qdrant. El servicio usa el código de `/opt/catalina`.
La rama base es `main`. Prueba los cambios en una copia aislada antes de actualizar
esa carpeta y reiniciar la API. La configuración real de systemd/Nginx y el esquema
inicial completo de PostgreSQL todavía no están versionados en este repositorio.

El historial de mensajes todavía no conserva el detalle de las fuentes citadas;
el frontend muestra las fuentes de respuestas nuevas durante la sesión.
