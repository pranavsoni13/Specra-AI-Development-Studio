from pathlib import Path

from app.rag.embeddings import LocalEmbeddingModel
from app.rag.schemas import KnowledgeChunk
from app.rag.vector_store import LocalVectorStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWLEDGE_DIRECTORY = (
    PROJECT_ROOT / "knowledge" / "documents"
)


CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero."
        )

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be >= 0 and smaller than chunk_size."
        )

    words = text.split()

    if not words:
        return []

    chunks = []

    start = 0

    while start < len(words):

        end = min(
            start + chunk_size,
            len(words),
        )

        chunk = " ".join(
            words[start:end]
        ).strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(words):
            break

        start = end - overlap

    return chunks


def load_documents() -> list[KnowledgeChunk]:

    chunks = []

    documents = sorted(
        KNOWLEDGE_DIRECTORY.glob("*.md")
    )

    if not documents:
        raise FileNotFoundError(
            f"No knowledge documents found in "
            f"{KNOWLEDGE_DIRECTORY}"
        )

    for document_path in documents:

        text = document_path.read_text(
            encoding="utf-8"
        )

        document_id = document_path.stem

        document_chunks = split_text(text)

        for index, content in enumerate(
            document_chunks
        ):

            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{document_id}-{index}",
                    document_id=document_id,
                    content=content,
                    metadata={
                        "source": document_path.name,
                        "type": "engineering_knowledge",
                    },
                )
            )

    return chunks


def main():

    print(
        "Loading knowledge documents..."
    )

    chunks = load_documents()

    print(
        f"Created {len(chunks)} knowledge chunks."
    )

    embedding_model = LocalEmbeddingModel()

    print(
        "Generating embeddings..."
    )

    embeddings = embedding_model.embed(
        [
            chunk.content
            for chunk in chunks
        ]
    )

    vector_store = LocalVectorStore()

    print(
        "Writing embeddings to vector database..."
    )

    vector_store.add_chunks(
        chunks,
        embeddings,
    )

    print(
        f"Vector database now contains "
        f"{vector_store.count()} chunks."
    )

    print(
        "Knowledge ingestion complete."
    )


if __name__ == "__main__":
    main()