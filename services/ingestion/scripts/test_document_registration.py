import asyncio
import sys
from io import BytesIO

from fastapi import UploadFile

from catalina_ingestion.db.postgres import (
    close_postgres_pool,
    open_postgres_pool,
)
from catalina_ingestion.domain.exceptions import (
    DuplicateFileError,
    IngestionError,
)
from catalina_ingestion.schemas.documents import (
    DocumentRegistrationRequest,
)
from catalina_ingestion.services.document_registration import (
    DocumentRegistrationService,
)
from catalina_ingestion.services.staging import StagingService

TEST_CONTENT = (
    b"Documento de prueba tecnica del servicio de ingesta Catalina.\n"
    b"Este contenido permite validar el registro, almacenamiento, "
    b"versionado y deteccion de duplicados.\n"
)


async def create_validated_file():
    upload = UploadFile(
        filename="prueba_ingesta_catalina.txt",
        file=BytesIO(TEST_CONTENT),
    )

    return await StagingService().receive(upload)


async def main() -> int:
    await open_postgres_pool()

    registration_request = DocumentRegistrationRequest(
        codigo="prueba-tecnica-ingesta",
        nombre="Prueba técnica del servicio de ingesta",
        categoria="faq",
        version="1.0.0",
        descripcion=("Documento controlado para validar la Fase 4.6."),
        idioma="es",
        origen="prueba-interna",
        metadatos={
            "tipo": "prueba_integracion",
            "fase": "4.6",
        },
    )

    service = DocumentRegistrationService()

    try:
        first_file = await create_validated_file()

        first_result = await service.register(
            first_file,
            registration_request,
        )

        print("PRIMERA CARGA: CORRECTA")
        print(first_result.model_dump_json(indent=2))

        duplicate_file = await create_validated_file()

        try:
            await service.register(
                duplicate_file,
                registration_request,
            )
        except DuplicateFileError as error:
            print("SEGUNDA CARGA: DUPLICADO DETECTADO CORRECTAMENTE")
            print(f"codigo={error.code}")
            print(f"detalle={error.message}")
            print(f"datos={error.details}")
        else:
            print(
                "ERROR: la segunda carga no fue detectada como duplicada.",
                file=sys.stderr,
            )
            return 1

    except IngestionError as error:
        print(
            f"ERROR CONTROLADO: {error.code}: {error.message}",
            file=sys.stderr,
        )
        print(f"datos={error.details}", file=sys.stderr)
        return 1
    except Exception as error:
        print(
            f"ERROR INESPERADO: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1
    finally:
        await close_postgres_pool()

    print("PRUEBA INTEGRAL DE REGISTRO: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
