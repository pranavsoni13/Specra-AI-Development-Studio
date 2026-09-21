from pathlib import Path

import chromadb

from .schemas import KnowledgeChunk


DEFAULT_VECTOR_DATABASE_PATH = "knowledge/vector_db"
DEFAULT_COLLECTION_NAME = "engineering_knowledge"


class LocalVectorStore:
    """
    Persistent local Chroma vector database.
    """

    def __init__(
        self,
        database_path: str = DEFAULT_VECTOR_DATABASE_PATH,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ):
        self.database_path = Path(database_path)

        self.database_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = chromadb.PersistentClient(
            path=str(self.database_path)
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "description": (
                    "Engineering knowledge for AI Development Studio"
                )
            },
        )

    def add_chunks(
        self,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError(
                "Number of chunks must match number of embeddings."
            )

        if not chunks:
            return

        self.collection.upsert(
            ids=[
                chunk.chunk_id
                for chunk in chunks
            ],
            embeddings=embeddings,
            documents=[
                chunk.content
                for chunk in chunks
            ],
            metadatas=[
                {
                    "document_id": chunk.document_id,
                    **chunk.metadata,
                }
                for chunk in chunks
            ],
        )

    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
        )

        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        results = []

        for index, chunk_id in enumerate(ids):
            metadata = metadatas[index] or {}

            results.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": metadata.get(
                        "document_id",
                        "",
                    ),
                    "content": documents[index],
                    "metadata": metadata,
                    "distance": distances[index],
                }
            )

        return results

    def count(self) -> int:
        return self.collection.count()