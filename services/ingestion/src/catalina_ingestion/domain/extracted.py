from dataclasses import dataclass, field
from typing import Any, Literal

BlockType = Literal["heading", "paragraph", "list", "table"]


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    index: int
    text: str
    block_type: BlockType
    page_number: int | None
    section: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    title: str | None
    page_count: int | None
    blocks: list[ExtractedBlock]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks if block.text.strip())

    @property
    def section_count(self) -> int:
        return len({block.section for block in self.blocks if block.section is not None})
