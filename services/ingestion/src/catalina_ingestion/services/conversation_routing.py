"""Route standalone social messages; mixed questions always retain documentary retrieval."""

import re
import unicodedata


def conversational_reply(query: str) -> str | None:
    normalized = unicodedata.normalize("NFKD", query.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    rules = (
        (r"(?:hola|buenas|buenos dias|buenas tardes|buenas noches|hey|que tal)"
         r"(?: catalina)?(?: como estas| como te va)?",
         "¡Hola! Soy Catalina. ¿En qué te puedo ayudar hoy?"),
        (r"(?:como estas|como te va)(?: catalina)?",
         "¡Hola! Estoy lista para ayudarte. ¿Qué te gustaría consultar?"),
        (r"(?:muchas )?gracias(?: catalina| por tu ayuda)?|(?:ok|vale|perfecto|entendido)",
         "¡Con gusto! Si tienes otra pregunta, aquí estoy para ayudarte."),
        (r"(?:adios|hasta luego|chao|nos vemos)(?: catalina)?",
         "¡Hasta luego! Aquí estaré cuando necesites ayuda."),
        (r"(?:quien eres|como te llamas|que puedes hacer|en que puedes ayudarme)"
         r"(?: catalina)?",
         "Soy Catalina, tu asistente universitario. Puedo orientarte sobre trámites, "
         "reglamentos, calendario y servicios de la universidad consultando documentos "
         "institucionales y mostrando sus fuentes. ¿Qué necesitas saber?"),
    )
    for pattern, reply in rules:
        if re.fullmatch(pattern, normalized):
            return reply
    return None
