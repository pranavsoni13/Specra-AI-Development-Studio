from pydantic import BaseModel, Field


class KnowledgeChunk(BaseModel):
    """
    A chunk of knowledge stored in the vector database.
    """

    chunk_id: str = Field(
        description="Unique identifier for the knowledge chunk"
    )

    document_id: str = Field(
        description="Identifier of the source document"
    )

    content: str = Field(
        description="Text content of the knowledge chunk"
    )

    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Metadata associated with the chunk"
    )


class RetrievedKnowledge(BaseModel):
    """
    Knowledge retrieved from the vector database.
    """

    chunk: KnowledgeChunk

    distance: float = Field(
        description="Vector similarity distance"
    )