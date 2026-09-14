from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalFilter:
    document_id: int | None = None
    document_version_id: int | None = None
    category: str | None = None
    language: str | None = None
    version: str | None = None
    section: str | None = None
    page_from: int | None = None
    page_to: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "document_version_id",
            "page_from",
            "page_to",
        ):
            value = getattr(self, name)

            if value is not None:
                if type(value) is not int or value < 1:
                    raise ValueError(f"{name} debe ser un entero positivo.")

        for name in (
            "category",
            "language",
            "version",
            "section",
        ):
            value = getattr(self, name)

            if value is None:
                continue

            if not isinstance(value, str):
                raise ValueError(f"{name} debe ser texto.")

            normalized = value.strip()

            if not normalized:
                raise ValueError(f"{name} no puede estar vacío.")

            if len(normalized) > 500:
                raise ValueError(f"{name} supera los 500 caracteres permitidos.")

            object.__setattr__(self, name, normalized)

        if (
            self.page_from is not None
            and self.page_to is not None
            and self.page_from > self.page_to
        ):
            raise ValueError("page_from no puede ser mayor que page_to.")
