from sentence_transformers import SentenceTransformer


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class LocalEmbeddingModel:
    """
    Local embedding model used for semantic retrieval.

    No external API is required.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
    ):
        self.model_name = model_name

        self.model = SentenceTransformer(
            model_name,
            device="cpu",
        )

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        return self.model.encode(
            texts,
            normalize_embeddings=True,
        ).tolist()