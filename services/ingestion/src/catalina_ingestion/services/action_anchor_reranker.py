import math
import re
import unicodedata
from collections.abc import Iterable

from catalina_ingestion.domain.retrieval import RetrievedChunk

ACTION_STEMS = frozenset(
    {
        "modific",
        "aprob",
        "derog",
        "adopt",
        "adicion",
        "prorrog",
        "reform",
        "actualiz",
        "sustitu",
        "expidi",
        "estableci",
    }
)

WORD_PATTERN = re.compile(r"[a-z0-9]+")


def normalize_anchor_text(text: str | None) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        (text or "").casefold(),
    )

    return "".join(character for character in normalized if not unicodedata.combining(character))


def extract_action_stems(text: str | None) -> frozenset[str]:
    words = WORD_PATTERN.findall(normalize_anchor_text(text))

    found: set[str] = set()

    for word in words:
        for stem in ACTION_STEMS:
            if word.startswith(stem):
                found.add(stem)

    return frozenset(found)


def chunk_matches_actions(
    query_actions: frozenset[str],
    chunk: RetrievedChunk,
) -> bool:
    if not query_actions:
        return False

    candidate_actions = extract_action_stems(chunk.document_name) | extract_action_stems(
        chunk.section
    )

    return bool(query_actions & candidate_actions)


class ActionAnchorReranker:
    def __init__(
        self,
        bonus: float = 0.15,
    ) -> None:
        if type(bonus) not in (int, float) or not math.isfinite(bonus) or bonus < 0:
            raise ValueError("bonus debe ser un número finito mayor o igual a cero.")

        self.bonus = float(bonus)

    def rank(
        self,
        query: str,
        chunks: Iterable[RetrievedChunk],
    ) -> tuple[RetrievedChunk, ...]:
        query_actions = extract_action_stems(query)

        def ranking_key(
            chunk: RetrievedChunk,
        ) -> tuple[float, float, str]:
            action_match = chunk_matches_actions(
                query_actions,
                chunk,
            )

            ranking_score = chunk.score + (self.bonus if action_match else 0.0)

            return (
                -ranking_score,
                -chunk.score,
                chunk.point_id,
            )

        return tuple(
            sorted(
                chunks,
                key=ranking_key,
            )
        )
