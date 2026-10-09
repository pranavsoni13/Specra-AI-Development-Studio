from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.embeddings import LocalEmbeddingModel
from app.rag.schemas import KnowledgeChunk, RetrievedKnowledge
from app.rag.vector_store import LocalVectorStore


DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class ProjectContextChunk:
    chunk_id: str
    context_id: str
    project_id: str
    content: str
    metadata: dict[str, str]


def project_collection_name(project_id: str) -> str:
    safe_project_id = re.sub(
        r"[^a-zA-Z0-9_-]",
        "",
        project_id,
    )

    if not safe_project_id:
        raise ValueError(
            "Project ID cannot produce a valid collection name."
        )

    return f"project_context_{safe_project_id}"[:63]


class ProjectContextChunker:
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        if chunk_size < 200:
            raise ValueError(
                "chunk_size must be at least 200 characters."
            )

        if chunk_overlap < 0:
            raise ValueError(
                "chunk_overlap cannot be negative."
            )

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, content: str) -> list[str]:
        text = content.strip()

        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(
                r"\n\s*\n",
                text,
            )
            if paragraph.strip()
        ]

        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            if not current:
                if len(paragraph) <= self.chunk_size:
                    current = paragraph
                    continue

                chunks.extend(
                    self._split_long_text(
                        paragraph
                    )
                )
                continue

            candidate = f"{current}\n\n{paragraph}"

            if len(candidate) <= self.chunk_size:
                current = candidate
                continue

            chunks.append(current)

            overlap_source = current[
                -self.chunk_overlap:
            ]

            current = (
                f"{overlap_source}\n\n{paragraph}"
                if overlap_source
                else paragraph
            )

            if len(current) > self.chunk_size:
                chunks.extend(
                    self._split_long_text(current)
                )
                current = ""

        if current:
            chunks.append(current)

        return [
            chunk.strip()
            for chunk in chunks
            if chunk.strip()
        ]

    def _split_long_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(
                start + self.chunk_size,
                text_length,
            )

            if end < text_length:
                whitespace = text.rfind(
                    " ",
                    start,
                    end,
                )

                if whitespace > start + 200:
                    end = whitespace

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            start = max(
                end - self.chunk_overlap,
                start + 1,
            )

        return chunks


class ProjectContextIndexer:
    """
    Index project-private context into a dedicated Chroma collection.

    Global engineering knowledge remains in the existing
    engineering_knowledge collection.
    """

    def __init__(
        self,
        embedding_model: LocalEmbeddingModel | None = None,
        vector_database_path: str = "knowledge/vector_db",
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        self.embedding_model = (
            embedding_model
            or LocalEmbeddingModel()
        )

        self.chunker = ProjectContextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        self.vector_database_path = vector_database_path

    def _vector_store(
        self,
        project_id: str,
    ) -> LocalVectorStore:
        return LocalVectorStore(
            database_path=self.vector_database_path,
            collection_name=project_collection_name(
                project_id
            ),
        )

    def build_chunks(
        self,
        context_record: dict,
    ) -> list[KnowledgeChunk]:
        project_id = context_record["project_id"]
        context_id = context_record["context_id"]

        pieces = self.chunker.split(
            context_record["content"]
        )

        chunks: list[KnowledgeChunk] = []

        for index, piece in enumerate(pieces):
            chunks.append(
                KnowledgeChunk(
                    chunk_id=(
                        f"ctx-{context_id}-{index:04d}"
                    ),
                    document_id=context_id,
                    content=piece,
                    metadata={
                        "project_id": project_id,
                        "context_id": context_id,
                        "source_name": context_record[
                            "name"
                        ],
                        "source_kind": context_record[
                            "kind"
                        ],
                        "chunk_index": str(index),
                        "chunk_count": str(
                            len(pieces)
                        ),
                    },
                )
            )

        return chunks

    def index_context(
        self,
        context_record: dict,
    ) -> int:
        project_id = context_record["project_id"]
        context_id = context_record["context_id"]

        chunks = self.build_chunks(context_record)

        self.delete_context(
            project_id,
            context_id,
        )

        if not chunks:
            return 0

        embeddings = self.embedding_model.embed(
            [
                chunk.content
                for chunk in chunks
            ]
        )

        self._vector_store(project_id).add_chunks(
            chunks,
            embeddings,
        )

        return len(chunks)

    def delete_context(
        self,
        project_id: str,
        context_id: str,
    ) -> None:
        self._vector_store(
            project_id
        ).collection.delete(
            where={
                "context_id": context_id
            }
        )

    def clear_project(
        self,
        project_id: str,
    ) -> None:
        self._vector_store(
            project_id
        ).collection.delete()

    def count_project_chunks(
        self,
        project_id: str,
    ) -> int:
        return self._vector_store(
            project_id
        ).count()


class ProjectKnowledgeRetriever:
    """
    Semantic retrieval over one project's private context.
    """

    def __init__(
        self,
        embedding_model: LocalEmbeddingModel | None = None,
        vector_database_path: str = "knowledge/vector_db",
    ):
        self.embedding_model = (
            embedding_model
            or LocalEmbeddingModel()
        )

        self.vector_database_path = (
            vector_database_path
        )

    def retrieve(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedKnowledge]:
        if not project_id or not project_id.strip():
            raise ValueError(
                "Project ID cannot be empty."
            )

        if not query or not query.strip():
            raise ValueError(
                "Retrieval query cannot be empty."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        vector_store = LocalVectorStore(
            database_path=self.vector_database_path,
            collection_name=project_collection_name(
                project_id
            ),
        )

        if vector_store.count() == 0:
            return []

        query_embedding = self.embedding_model.embed(
            [query.strip()]
        )[0]

        results = vector_store.search(
            embedding=query_embedding,
            top_k=top_k,
        )

        return [
            RetrievedKnowledge(
                chunk=KnowledgeChunk(
                    chunk_id=result["chunk_id"],
                    document_id=result["document_id"],
                    content=result["content"],
                    metadata={
                        str(key): str(value)
                        for key, value in result[
                            "metadata"
                        ].items()
                        if key != "document_id"
                    },
                ),
                distance=float(
                    result["distance"]
                ),
            )
            for result in results
        ]
