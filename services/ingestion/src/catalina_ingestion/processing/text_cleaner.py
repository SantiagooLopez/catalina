import re
import unicodedata

from catalina_ingestion.domain.extracted import BlockType

CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HYPHENATED_LINE_BREAK = re.compile(r"(?<=\w)-\s*\n\s*(?=\w)")
MULTIPLE_SPACES = re.compile(r"[ \t]+")
MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")


class TextCleaner:
    def clean(
        self,
        text: str,
        block_type: BlockType,
    ) -> str:
        cleaned = unicodedata.normalize("NFKC", text)
        cleaned = cleaned.replace("\u00ad", "")
        cleaned = cleaned.replace("\r\n", "\n")
        cleaned = cleaned.replace("\r", "\n")
        cleaned = CONTROL_CHARACTERS.sub("", cleaned)
        cleaned = HYPHENATED_LINE_BREAK.sub("", cleaned)

        lines = [MULTIPLE_SPACES.sub(" ", line).strip() for line in cleaned.splitlines()]

        if block_type in {"table", "list"}:
            cleaned = "\n".join(line for line in lines if line)
        else:
            cleaned = " ".join(line for line in lines if line)

        cleaned = MULTIPLE_BLANK_LINES.sub("\n\n", cleaned)
        return cleaned.strip()
