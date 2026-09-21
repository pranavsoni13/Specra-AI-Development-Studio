from .embeddings import LocalEmbeddingModel
from .schemas import KnowledgeChunk, RetrievedKnowledge
from .vector_store import LocalVectorStore


class KnowledgeRetriever:
    """
    Performs semantic retrieval from the local vector database.
    """

    def __init__(
        self,
        embedding_model: LocalEmbeddingModel | None = None,
        vector_store: LocalVectorStore | None = None,
    ):
        self.embedding_model = (
            embedding_model
            or LocalEmbeddingModel()
        )

        self.vector_store = (
            vector_store
            or LocalVectorStore()
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedKnowledge]:
        if not query or not query.strip():
            raise ValueError(
                "Retrieval query cannot be empty."
            )

        query_embedding = self.embedding_model.embed(
            [query.strip()]
        )[0]

        results = self.vector_store.search(
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
                        for key, value in result["metadata"].items()
                        if key != "document_id"
                    },
                ),
                distance=float(
                    result["distance"]
                ),
            )
            for result in results
        ]