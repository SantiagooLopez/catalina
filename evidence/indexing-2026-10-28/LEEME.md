# Evidencia real del índice activo

Consulta ejecutada en catalina-server el 28 de octubre de 2026, a las 21:59 UTC.
Se consultó PostgreSQL en una transacción de solo lectura y se realizó un conteo exacto
en Qdrant filtrado por el UUID de la misma ejecución. No se reindexaron documentos.

- `datos-reales.json`: datos obtenidos de los dos servicios.
- `salida-real.txt`: salida original del comando ejecutado por SSH.
- `captura-indexacion.png`: captura en navegador del archivo de texto anterior,
  sin sustituir valores ni simular una terminal. Es un reporte de consulta real.

El estado `activa` representa la ejecución publicada que utiliza la versión documental.
La indexación terminó en la fecha de finalización indicada; esta captura no muestra un
proceso de ingesta trabajando en tiempo real.

Para repetir en Debian con la copia temporal del script:

```bash
cd /opt/catalina/services/ingestion
PYTHONPATH=src .venv/bin/python /tmp/capture_indexing_evidence.py --output /tmp/catalina-indexing-evidence.json
```

El script de origen está en la copia Windows del repositorio, en
`services/ingestion/scripts/capture_indexing_evidence.py`. La copia de `/tmp` puede
desaparecer al reiniciar; el origen local permite transferirlo y repetir la consulta.
