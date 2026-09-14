import re
import unicodedata
import zipfile
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup
from charset_normalizer import from_bytes

from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.domain.exceptions import FileValidationError
from catalina_ingestion.domain.files import FileInspection


class FileValidator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate_filename(self, filename: str | None) -> tuple[str, str]:
        if not filename:
            raise FileValidationError(
                "FILE_NAME_MISSING",
                "El archivo no tiene nombre.",
            )

        normalized = unicodedata.normalize("NFKC", filename).strip()

        if not normalized:
            raise FileValidationError(
                "FILE_NAME_EMPTY",
                "El nombre del archivo está vacío.",
            )

        if len(normalized) > 255:
            raise FileValidationError(
                "FILE_NAME_TOO_LONG",
                "El nombre supera los 255 caracteres.",
            )

        if (
            Path(normalized).name != normalized
            or "/" in normalized
            or "\\" in normalized
            or "\x00" in normalized
        ):
            raise FileValidationError(
                "UNSAFE_FILE_NAME",
                "El nombre contiene una ruta o caracteres inseguros.",
            )

        if any(ord(character) < 32 for character in normalized):
            raise FileValidationError(
                "UNSAFE_FILE_NAME",
                "El nombre contiene caracteres de control.",
            )

        extension = Path(normalized).suffix.lower()

        if extension not in self.settings.allowed_extensions:
            raise FileValidationError(
                "EXTENSION_NOT_ALLOWED",
                f"La extensión {extension or '(sin extensión)'} no está permitida.",
            )

        safe_name = re.sub(
            r"[^\w.\- ]",
            "_",
            normalized,
            flags=re.UNICODE,
        )
        safe_name = re.sub(r"\s+", "_", safe_name).strip("._")

        if not safe_name:
            raise FileValidationError(
                "UNSAFE_FILE_NAME",
                "No fue posible generar un nombre seguro.",
            )

        return safe_name, extension

    def inspect(self, path: Path, extension: str) -> FileInspection:
        inspectors = {
            ".pdf": self._inspect_pdf,
            ".docx": self._inspect_docx,
            ".txt": self._inspect_text,
            ".html": self._inspect_html,
            ".htm": self._inspect_html,
        }

        inspector = inspectors.get(extension)

        if inspector is None:
            raise FileValidationError(
                "FORMAT_NOT_SUPPORTED",
                f"No existe un extractor para {extension}.",
            )

        return inspector(path)

    def _inspect_pdf(self, path: Path) -> FileInspection:
        with path.open("rb") as file:
            signature = file.read(5)

        if signature != b"%PDF-":
            raise FileValidationError(
                "INVALID_PDF_SIGNATURE",
                "El archivo no contiene una firma PDF válida.",
            )

        try:
            document = pymupdf.open(path)
        except Exception as error:
            raise FileValidationError(
                "CORRUPTED_PDF",
                "El archivo PDF está dañado o no puede abrirse.",
            ) from error

        try:
            if document.needs_pass:
                raise FileValidationError(
                    "ENCRYPTED_PDF",
                    "Los PDF protegidos con contraseña no están permitidos.",
                )

            if document.page_count < 1:
                raise FileValidationError(
                    "EMPTY_PDF",
                    "El PDF no contiene páginas.",
                )

            page_count = document.page_count
        finally:
            document.close()

        return FileInspection(
            mime_type="application/pdf",
            page_count=page_count,
        )

    def _inspect_docx(self, path: Path) -> FileInspection:
        if not zipfile.is_zipfile(path):
            raise FileValidationError(
                "INVALID_DOCX",
                "El archivo no tiene una estructura DOCX válida.",
            )

        required_entries = {
            "[Content_Types].xml",
            "word/document.xml",
        }

        try:
            with zipfile.ZipFile(path) as archive:
                archive_entries = set(archive.namelist())

                if not required_entries.issubset(archive_entries):
                    raise FileValidationError(
                        "INVALID_DOCX",
                        "El archivo comprimido no contiene un documento Word.",
                    )

                corrupted_entry = archive.testzip()

                if corrupted_entry is not None:
                    raise FileValidationError(
                        "CORRUPTED_DOCX",
                        f"El componente {corrupted_entry} está dañado.",
                    )
        except FileValidationError:
            raise
        except Exception as error:
            raise FileValidationError(
                "CORRUPTED_DOCX",
                "No fue posible validar el documento Word.",
            ) from error

        return FileInspection(
            mime_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        )

    def _inspect_text(self, path: Path) -> FileInspection:
        text, encoding = self._decode_text_sample(path)

        if not text.strip():
            raise FileValidationError(
                "EMPTY_TEXT_FILE",
                "El archivo de texto no contiene información.",
            )

        return FileInspection(
            mime_type="text/plain",
            encoding=encoding,
        )

    def _inspect_html(self, path: Path) -> FileInspection:
        text, encoding = self._decode_text_sample(path)

        if not text.strip():
            raise FileValidationError(
                "EMPTY_HTML_FILE",
                "El archivo HTML está vacío.",
            )

        soup = BeautifulSoup(text, "html.parser")

        if soup.find() is None:
            raise FileValidationError(
                "INVALID_HTML",
                "El archivo no contiene una estructura HTML reconocible.",
            )

        return FileInspection(
            mime_type="text/html",
            encoding=encoding,
        )

    def _decode_text_sample(self, path: Path) -> tuple[str, str]:
        with path.open("rb") as file:
            sample = file.read(2 * 1024 * 1024)

        result = from_bytes(sample).best()

        if result is None or result.chaos > 0.30:
            raise FileValidationError(
                "BINARY_CONTENT",
                "El archivo parece contener información binaria.",
            )

        return str(result), result.encoding
