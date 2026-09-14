from catalina_ingestion.domain.extracted import (
    ExtractedBlock,
    ExtractedDocument,
)
from catalina_ingestion.processing.chunker import DocumentChunker
from catalina_ingestion.processing.structure import (
    StructureProcessor,
)
from catalina_ingestion.processing.text_cleaner import (
    TextCleaner,
)


def create_block(
    index,
    text,
    block_type="paragraph",
    page=1,
    section=None,
):
    return ExtractedBlock(
        index=index,
        text=text,
        block_type=block_type,
        page_number=page,
        section=section,
    )


def test_cleans_whitespace_and_hyphenated_line_break():
    cleaner = TextCleaner()

    result = cleaner.clean(
        "La univer-\nsidad   ofrece\tservicios.",
        "paragraph",
    )

    assert result == "La universidad ofrece servicios."


def test_removes_repeated_headers_and_page_numbers():
    blocks = []
    index = 0

    for page in range(1, 4):
        blocks.append(
            create_block(
                index,
                "Universidad Católica de Colombia",
                page=page,
            )
        )
        index += 1

        blocks.append(
            create_block(
                index,
                f"Contenido académico de la página {page}.",
                page=page,
            )
        )
        index += 1

        blocks.append(create_block(index, str(page), page=page))
        index += 1

    document = ExtractedDocument(
        title="Documento",
        page_count=3,
        blocks=blocks,
    )

    processed, removed = StructureProcessor().process(document)

    texts = [block.text for block in processed]

    assert "Universidad Católica de Colombia" not in texts
    assert "1" not in texts
    assert "2" not in texts
    assert "3" not in texts
    assert removed == 6


def test_promotes_numbered_paragraph_to_heading():
    document = ExtractedDocument(
        title=None,
        page_count=1,
        blocks=[
            create_block(
                0,
                "1. Derechos de los estudiantes",
            ),
            create_block(
                1,
                "Los estudiantes tienen derecho a participar.",
            ),
        ],
    )

    processed, _ = StructureProcessor().process(document)

    assert processed[0].block_type == "heading"
    assert processed[1].section == "1. Derechos de los estudiantes"


def test_chunks_do_not_cross_sections():
    blocks = [
        create_block(
            0,
            "SECCIÓN UNO",
            "heading",
            section="SECCIÓN UNO",
        ),
        create_block(
            1,
            "Contenido de la primera sección.",
            section="SECCIÓN UNO",
        ),
        create_block(
            2,
            "SECCIÓN DOS",
            "heading",
            section="SECCIÓN DOS",
        ),
        create_block(
            3,
            "Contenido de la segunda sección.",
            section="SECCIÓN DOS",
        ),
    ]

    extracted = ExtractedDocument(
        title=None,
        page_count=1,
        blocks=blocks,
    )
    processed, _ = StructureProcessor().process(extracted)

    chunks = DocumentChunker(
        target_size=50,
        overlap=5,
        minimum_size=5,
    ).create_chunks(processed)

    assert len(chunks) == 2
    assert chunks[0].section == "SECCIÓN UNO"
    assert chunks[1].section == "SECCIÓN DOS"


def test_chunk_hashes_are_reproducible():
    document = ExtractedDocument(
        title=None,
        page_count=1,
        blocks=[
            create_block(
                0,
                "Contenido institucional reproducible.",
            )
        ],
    )

    processed, _ = StructureProcessor().process(document)
    chunker = DocumentChunker(
        target_size=50,
        overlap=5,
        minimum_size=5,
    )

    first = chunker.create_chunks(processed)
    second = chunker.create_chunks(processed)

    assert first[0].text_sha256 == second[0].text_sha256


def test_splits_oversized_block():
    document = ExtractedDocument(
        title=None,
        page_count=1,
        blocks=[
            create_block(
                0,
                " ".join(f"palabra{number}" for number in range(100)),
            )
        ],
    )

    processed, _ = StructureProcessor().process(document)

    chunks = DocumentChunker(
        target_size=20,
        overlap=5,
        minimum_size=5,
    ).create_chunks(processed)

    assert len(chunks) > 1
    assert all(chunk.estimated_tokens <= 25 for chunk in chunks)
