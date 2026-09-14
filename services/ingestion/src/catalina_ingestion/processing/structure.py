import math
import re
from collections import Counter, defaultdict

from catalina_ingestion.domain.extracted import ExtractedDocument
from catalina_ingestion.domain.processed import ProcessedBlock
from catalina_ingestion.processing.text_cleaner import TextCleaner

PAGE_NUMBER_PATTERN = re.compile(
    r"^(p[aá]gina\s*)?\d+(\s*(de|/)\s*\d+)?$",
    re.IGNORECASE,
)

NUMBERED_HEADING_PATTERN = re.compile(
    r"^(\d+(\.\d+)*|art[ií]culo\s+\d+)[.)]?\s+\S+",
    re.IGNORECASE,
)


class StructureProcessor:
    def __init__(
        self,
        cleaner: TextCleaner | None = None,
    ) -> None:
        self.cleaner = cleaner or TextCleaner()

    def process(
        self,
        document: ExtractedDocument,
    ) -> tuple[list[ProcessedBlock], int]:
        initially_cleaned = self._clean_blocks(document)
        repeated_indexes = self._find_repeated_indexes(
            initially_cleaned,
            document.page_count,
        )

        processed: list[ProcessedBlock] = []
        current_section: str | None = None

        for block in initially_cleaned:
            if block.source_index in repeated_indexes:
                continue

            block_type = block.block_type

            if block_type == "paragraph" and self._looks_like_heading(block.text):
                block_type = "heading"

            if block_type == "heading":
                current_section = block.text
            elif block.section:
                current_section = block.section

            processed.append(
                ProcessedBlock(
                    index=len(processed),
                    source_index=block.source_index,
                    text=block.text,
                    block_type=block_type,
                    page_number=block.page_number,
                    section=current_section,
                    metadata=block.metadata,
                )
            )

        return processed, len(repeated_indexes)

    def _clean_blocks(
        self,
        document: ExtractedDocument,
    ) -> list[ProcessedBlock]:
        cleaned_blocks: list[ProcessedBlock] = []

        for block in document.blocks:
            cleaned_text = self.cleaner.clean(
                block.text,
                block.block_type,
            )

            if not cleaned_text:
                continue

            cleaned_blocks.append(
                ProcessedBlock(
                    index=len(cleaned_blocks),
                    source_index=block.index,
                    text=cleaned_text,
                    block_type=block.block_type,
                    page_number=block.page_number,
                    section=block.section,
                    metadata=block.metadata,
                )
            )

        return cleaned_blocks

    def _find_repeated_indexes(
        self,
        blocks: list[ProcessedBlock],
        page_count: int | None,
    ) -> set[int]:
        if page_count is None or page_count < 3:
            return self._find_page_number_indexes(blocks)

        by_page: dict[int, list[ProcessedBlock]] = defaultdict(list)

        for block in blocks:
            if block.page_number is not None:
                by_page[block.page_number].append(block)

        candidates: list[ProcessedBlock] = []

        for page_blocks in by_page.values():
            if not page_blocks:
                continue

            candidates.append(page_blocks[0])

            if len(page_blocks) > 1:
                candidates.append(page_blocks[-1])

        fingerprints = Counter(
            self._fingerprint(block.text) for block in candidates if len(block.text) <= 200
        )

        repetition_threshold = max(
            3,
            math.ceil(page_count * 0.60),
        )

        repeated_fingerprints = {
            fingerprint
            for fingerprint, count in fingerprints.items()
            if count >= repetition_threshold
        }

        repeated_indexes = {
            block.source_index
            for block in candidates
            if self._fingerprint(block.text) in repeated_fingerprints
        }

        repeated_indexes.update(self._find_page_number_indexes(blocks))

        return repeated_indexes

    def _find_page_number_indexes(
        self,
        blocks: list[ProcessedBlock],
    ) -> set[int]:
        return {
            block.source_index
            for block in blocks
            if PAGE_NUMBER_PATTERN.fullmatch(block.text.strip())
        }

    def _fingerprint(self, text: str) -> str:
        normalized = text.casefold()
        normalized = re.sub(r"\d+", "#", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _looks_like_heading(self, text: str) -> bool:
        if "\n" in text or len(text) > 180:
            return False

        if len(text.split()) > 20:
            return False

        return bool(
            NUMBERED_HEADING_PATTERN.match(text)
            or (text.isupper() and any(character.isalpha() for character in text))
        )
