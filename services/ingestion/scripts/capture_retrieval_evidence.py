"""Run the real managed retrieval pipeline and preserve its unmodified results."""

import asyncio
import json
import socket
from contextlib import AsyncExitStack
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from catalina_ingestion.clients.ollama import close_ollama_client, open_ollama_client
from catalina_ingestion.clients.qdrant import close_qdrant_client, open_qdrant_client
from catalina_ingestion.db.postgres import close_postgres_pool, open_postgres_pool
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.services.retrieval_runtime import ManagedRetrievalService

QUESTION = (
    "¿Qué reglamento rige actualmente a los estudiantes de la "
    "Universidad Católica de Colombia?"
)


async def main() -> None:
    async with AsyncExitStack() as stack:
        await open_postgres_pool()
        stack.push_async_callback(close_postgres_pool)
        await open_ollama_client()
        stack.push_async_callback(close_ollama_client)
        await open_qdrant_client()
        stack.push_async_callback(close_qdrant_client)
        query = RetrievalQuery(query=QUESTION)
        started = perf_counter()
        result = await ManagedRetrievalService().build(query)
        record = {
            "fecha_utc": datetime.now(UTC).isoformat(), "servidor": socket.gethostname(),
            "consulta": asdict(query), "duracion_segundos": round(perf_counter() - started, 3),
            "resultado": asdict(result),
        }
    output = Path("/tmp/catalina-retrieval-evidence.json")
    output.write_text(json.dumps(record, default=str, ensure_ascii=False, indent=2), "utf-8")
    print("CATALINA | EVIDENCIA REAL DE RECUPERACION DOCUMENTAL")
    print(f"Fecha UTC: {record['fecha_utc']} | Servidor: {record['servidor']}")
    print(f"Pregunta: {QUESTION}")
    print(f"Estado del contexto: {result.reason}")
    print(f"Contexto habilitado: {result.enabled}")
    print(f"Mejor puntuacion de la evidencia: {result.assessment.best_score}")
    print(f"Fuentes recuperadas: {len(result.sources)}")
    print(f"Duracion (s): {record['duracion_segundos']}")
    records = json.loads(result.text).get("sources", []) if result.text else []
    for source in result.sources[:3]:
        print(f"\nFUENTE [{source.citation_id}]")
        print(f"Documento: {source.document_name}")
        print(f"Version: {source.version} | ID version: {source.document_version_id}")
        print(f"Pagina: {source.page_start} - {source.page_end} | Seccion: {source.section}")
        print(f"ID documento: {source.document_id} | ID fragmento: {source.point_id}")
        match = next((item for item in records
                      if item.get("source", {}).get("point_id") == source.point_id), None)
        if match:
            print("Resultado recuperado (extracto literal, max. 700 caracteres):")
            print(match["text"][:700])
    print(f"\nResultado completo sin modificaciones: {output}")
    print("Consulta sin filtros documentales impuestos ni cambios de umbral.")


if __name__ == "__main__":
    asyncio.run(main())
