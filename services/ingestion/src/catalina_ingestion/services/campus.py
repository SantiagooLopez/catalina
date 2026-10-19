"""Curated campus directory. Image coordinates are reference pixels, never GPS positions."""

import json
import re
import unicodedata
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, Field

from catalina_ingestion.domain.generation import GeneratedAnswer, GenerationReason


class ReferencePoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class CampusSource(BaseModel):
    label: str
    url: str | None


class CampusLocation(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    category: Literal["sede", "facultad", "servicio", "dependencia", "referencia", "pendiente"]
    aliases: list[str]
    address: str | None
    source_id: str
    parent_id: str | None = None
    reference_point: ReferencePoint | None = None
    note: str


class CampusCatalog(BaseModel):
    reviewed_at: str
    reference_image: str
    reference_width: int = Field(gt=0)
    reference_height: int = Field(gt=0)
    google_maps_url: str
    sources: dict[str, CampusSource]
    locations: list[CampusLocation]


@lru_cache(maxsize=1)
def campus_catalog() -> CampusCatalog:
    text = files("catalina_ingestion.data").joinpath("campus_locations.json").read_text("utf-8")
    catalog = CampusCatalog.model_validate(json.loads(text))
    by_id = {place.id: place for place in catalog.locations}
    if len(by_id) != len(catalog.locations):
        raise ValueError("Identificadores de campus repetidos.")
    for place in catalog.locations:
        if place.source_id not in catalog.sources:
            raise ValueError("Fuente de campus inexistente.")
        visited = {place.id}
        parent_id = place.parent_id
        while parent_id is not None:
            if parent_id not in by_id or parent_id in visited:
                raise ValueError("Referencia de sede inexistente o circular.")
            visited.add(parent_id)
            parent_id = by_id[parent_id].parent_id
    return catalog


def normalize(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                            if not unicodedata.combining(c)).split())


def location_intent(query: str) -> bool:
    return bool(re.search(
        r"\b(?:donde\s+(?:queda\w*|esta\w*|encuentro|se encuentra\w*|se ubica\w*)|"
        r"ubicacion|ubicar|direccion|como\s+(?:puedo\s+)?(?:llego|llegar|ir)|"
        r"en que (?:sede|edificio)|en cual sede|mapa|plano|localiza\w*)\b", normalize(query),
    ))


def match_locations(query: str) -> list[CampusLocation]:
    text = normalize(query)
    hits = []
    for place in campus_catalog().locations:
        aliases = [normalize(alias) for alias in place.aliases]
        matches = [alias for alias in aliases
                   if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text)]
        if matches:
            hits.append((place, max(matches, key=len)))
    # An explicit 'biblioteca sede 4' wins over generic 'biblioteca' and 'sede 4'.
    return [place for place, alias in hits
            if not any(alias != other and alias in other for _, other in hits)]


def public_catalog() -> dict:
    catalog = campus_catalog()
    data = catalog.model_dump()
    by_id = {place.id: place for place in catalog.locations}
    for item, place in zip(data["locations"], catalog.locations, strict=True):
        parent = by_id.get(place.parent_id)
        item["resolved_address"] = place.address or (parent.address if parent else None)
        item["parent_name"] = parent.name if parent else None
        anchor = place if place.reference_point else parent
        item["anchor_id"] = anchor.id if anchor and anchor.reference_point else None
        item["source"] = catalog.sources[place.source_id].model_dump()
    return data


def directory_answer(
    query: str, *, selected_id: str | None = None, force: bool = False,
) -> GeneratedAnswer | None:
    catalog = campus_catalog()
    by_id = {place.id: place for place in catalog.locations}
    if selected_id is not None and selected_id not in by_id:
        raise ValueError("La dependencia seleccionada no existe en el mapa.")
    if not force and not location_intent(query):
        return None
    matches = match_locations(query)
    if not matches and not force:
        if not re.search(
            r"\b(?:universidad catolica de colombia|nuestra universidad|dependencia|"
            r"facultad|sede|rectoria|cafeteria|laboratorio)\b", normalize(query),
        ):
            return None
    text = normalize(query)
    if not matches and selected_id:
        matches = [by_id[selected_id]]

    if force and re.search(r"\b(?:horario\w*|abren|cierran|telefono|costo\w*)\b", text):
        reply = "El mapa no tiene ese dato verificado. Consulta el directorio institucional."
    elif force and not location_intent(query) and re.search(
        r"\b(?:que servicios|tramites|requisitos|procedimiento)\b", text,
    ):
        reply = (
            "Este directorio permite ubicar dependencias. Para conocer sus servicios o requisitos, "
            "consulta el chat principal; allí se pueden buscar documentos institucionales."
        )
    elif re.search(r"\b(?:que hay|que dependencias|cuales dependencias|que oficinas)\b", text):
        selected = matches[0] if matches else by_id.get(selected_id)
        parent = by_id.get(selected.parent_id) if selected else None
        sede = parent or selected
        children = [place for place in catalog.locations if sede and place.parent_id == sede.id]
        if children:
            matches = children
            reply = f"Entre las dependencias registradas en {sede.name} están:\n\n" + "\n".join(
                f"• {place.name}." for place in children
            ) + "\n\nLos pisos y oficinas exactos siguen pendientes de confirmar."
        else:
            reply = (
                f"No hay dependencias adicionales registradas para {sede.name}. {sede.note}"
                if sede else "Selecciona una sede para consultar sus dependencias registradas."
            )
    elif matches:
        paragraphs = []
        for place in matches:
            parent = by_id.get(place.parent_id)
            address = place.address or (parent.address if parent else None)
            paragraph = place.name
            if parent:
                paragraph += f" · {parent.name}"
            paragraph += f"\nDirección publicada: {address}." if address else (
                "\nLa dirección exacta está pendiente de confirmación."
            )
            paragraph += f"\n{place.note}"
            paragraphs.append(paragraph)
        reply = "\n\n".join(paragraphs)
        if len(matches) > 1:
            reply = (
                "Encontré varias ubicaciones; selecciona la que necesitas en el mapa:\n\n" + reply
            )
    else:
        reply = (
            "No tengo una ubicación confirmada para esa dependencia. Puedes explorar las sedes "
            "registradas o indicar su nombre completo; no voy a asignarle un marcador supuesto."
        )
    return GeneratedAnswer(
        query=query, text=reply, generated=False, reason=GenerationReason.CAMPUS_LOCATION,
        model=None, citations=(), locations=tuple(place.id for place in matches),
    )
