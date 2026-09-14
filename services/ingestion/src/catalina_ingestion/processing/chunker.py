import hashlib
import re
from dataclasses import dataclass

from catalina_ingestion.domain.extracted import BlockType
from catalina_ingestion.domain.processed import (
    DocumentChunk,
    ProcessedBlock,
)
from catalina_ingestion.processing.token_estimator import (
    TokenEstimator,
)

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?;:])\s+")


@dataclass(frozen=True, slots=True)
class TextUnit:
    text: str
    block_type: BlockType
    source_index: int
    page_number: int | None
    section: str | None
    estimated_tokens: int


class DocumentChunker:
    def __init__(
        self,
        target_size: int,
        overlap: int,
        minimum_size: int,
        token_estimator: TokenEstimator | None = None,
    ) -> None:
        if target_size <= 0:
            raise ValueError("target_size debe ser mayor que cero")

        if overlap < 0 or overlap >= target_size:
            raise ValueError("overlap debe ser positivo y menor que target_size")

        if minimum_size <= 0:
            raise ValueError("minimum_size debe ser mayor que cero")

        self.target_size = target_size
        self.overlap = overlap
        self.minimum_size = minimum_size
        self.token_estimator = token_estimator or TokenEstimator()

    def create_chunks(
        self,
        blocks: list[ProcessedBlock],
    ) -> list[DocumentChunk]:
        units = [unit for block in blocks for unit in self._split_block(block)]

        chunks: list[DocumentChunk] = []
        buffer: list[TextUnit] = []
        current_section: str | None = None

        for unit in units:
            section_changed = bool(buffer) and unit.section != current_section

            if section_changed:
                self._emit(buffer, chunks)
                buffer = []

            proposed_size = sum(item.estimated_tokens for item in buffer) + unit.estimated_tokens

            if buffer and proposed_size > self.target_size:
                previous_buffer = buffer
                self._emit(previous_buffer, chunks)

                overlap_units = self._overlap_tail(previous_buffer)

                overlap_size = sum(item.estimated_tokens for item in overlap_units)

                if overlap_size + unit.estimated_tokens > self.target_size:
                    overlap_units = []

                buffer = overlap_units

            buffer.append(unit)
            current_section = unit.section

        if buffer:
            self._emit(buffer, chunks)

        return self._merge_small_final_chunks(chunks)

    def _split_block(
        self,
        block: ProcessedBlock,
    ) -> list[TextUnit]:
        estimated = self.token_estimator.estimate(block.text)

        if estimated <= self.target_size:
            return [self._to_unit(block, block.text)]

        if block.block_type in {"table", "list"}:
            fragments = [line.strip() for line in block.text.splitlines() if line.strip()]
        else:
            fragments = [
                sentence.strip()
                for sentence in SENTENCE_BOUNDARY.split(block.text)
                if sentence.strip()
            ]

        expanded_fragments: list[str] = []

        for fragment in fragments:
            if self.token_estimator.estimate(fragment) <= self.target_size:
                expanded_fragments.append(fragment)
            else:
                expanded_fragments.extend(self._split_by_words(fragment))

        units: list[TextUnit] = []
        current_parts: list[str] = []
        current_size = 0

        for fragment in expanded_fragments:
            fragment_size = self.token_estimator.estimate(fragment)

            if current_parts and current_size + fragment_size > self.target_size:
                units.append(
                    self._to_unit(
                        block,
                        " ".join(current_parts),
                    )
                )
                current_parts = []
                current_size = 0

            current_parts.append(fragment)
            current_size += fragment_size

        if current_parts:
            units.append(
                self._to_unit(
                    block,
                    " ".join(current_parts),
                )
            )

        return units

    def _split_by_words(self, text: str) -> list[str]:
        words = text.split()
        fragments: list[str] = []
        current_words: list[str] = []
        current_size = 0

        for word in words:
            word_size = self.token_estimator.estimate(word)

            if current_words and current_size + word_size > self.target_size:
                fragments.append(" ".join(current_words))
                current_words = []
                current_size = 0

            current_words.append(word)
            current_size += word_size

        if current_words:
            fragments.append(" ".join(current_words))

        return fragments

    def _to_unit(
        self,
        block: ProcessedBlock,
        text: str,
    ) -> TextUnit:
        return TextUnit(
            text=text,
            block_type=block.block_type,
            source_index=block.source_index,
            page_number=block.page_number,
            section=block.section,
            estimated_tokens=self.token_estimator.estimate(text),
        )

    def _overlap_tail(
        self,
        units: list[TextUnit],
    ) -> list[TextUnit]:
        selected: list[TextUnit] = []
        selected_size = 0

        for unit in reversed(units):
            if selected and selected_size + unit.estimated_tokens > self.overlap:
                break

            if unit.estimated_tokens > self.overlap:
                continue

            selected.append(unit)
            selected_size += unit.estimated_tokens

        selected.reverse()
        return selected

    def _emit(
        self,
        units: list[TextUnit],
        chunks: list[DocumentChunk],
    ) -> None:
        if not units:
            return

        text = "\n\n".join(unit.text for unit in units).strip()

        if not text:
            return

        pages = sorted({unit.page_number for unit in units if unit.page_number is not None})

        source_indexes = tuple(dict.fromkeys(unit.source_index for unit in units))

        chunks.append(
            DocumentChunk(
                index=len(chunks),
                text=text,
                section=units[-1].section,
                page_start=pages[0] if pages else None,
                page_end=pages[-1] if pages else None,
                source_block_indexes=source_indexes,
                character_count=len(text),
                estimated_tokens=(self.token_estimator.estimate(text)),
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )

    def _merge_small_final_chunks(
        self,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        if len(chunks) < 2:
            return chunks

        merged: list[DocumentChunk] = []

        for chunk in chunks:
            if (
                merged
                and chunk.estimated_tokens < self.minimum_size
                and merged[-1].section == chunk.section
            ):
                previous = merged[-1]
                combined_text = f"{previous.text}\n\n{chunk.text}"
                combined_tokens = self.token_estimator.estimate(combined_text)

                if combined_tokens <= self.target_size + self.overlap:
                    pages = [
                        page
                        for page in (
                            previous.page_start,
                            previous.page_end,
                            chunk.page_start,
                            chunk.page_end,
                        )
                        if page is not None
                    ]

                    merged[-1] = DocumentChunk(
                        index=previous.index,
                        text=combined_text,
                        section=previous.section,
                        page_start=min(pages) if pages else None,
                        page_end=max(pages) if pages else None,
                        source_block_indexes=tuple(
                            dict.fromkeys(
                                previous.source_block_indexes + chunk.source_block_indexes
                            )
                        ),
                        character_count=len(combined_text),
                        estimated_tokens=combined_tokens,
                        text_sha256=hashlib.sha256(combined_text.encode("utf-8")).hexdigest(),
                    )
                    continue

            merged.append(chunk)

        return [
            DocumentChunk(
                index=index,
                text=chunk.text,
                section=chunk.section,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                source_block_indexes=(chunk.source_block_indexes),
                character_count=chunk.character_count,
                estimated_tokens=chunk.estimated_tokens,
                text_sha256=chunk.text_sha256,
            )
            for index, chunk in enumerate(merged)
        ]
