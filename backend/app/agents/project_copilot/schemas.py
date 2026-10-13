from typing import Literal

from pydantic import BaseModel, Field


ArtifactTarget = Literal[
    "requirements",
    "project_plan",
    "architecture",
    "technical_review",
]


class CopilotSourceRef(BaseModel):
    source_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)


class CopilotChangeProposal(BaseModel):
    target_artifact: ArtifactTarget
    summary: str = Field(min_length=3, max_length=600)
    rationale: str = Field(min_length=5, max_length=1200)
    suggested_instruction: str = Field(min_length=5, max_length=2400)


class CopilotAnswerDraft(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    source_refs: list[str] = Field(default_factory=list, max_length=24)
    proposed_changes: list[CopilotChangeProposal] = Field(default_factory=list, max_length=8)


class CopilotMessage(BaseModel):
    message_id: int
    role: Literal["user", "assistant"]
    content: str
    source_refs: list[str] = Field(default_factory=list)
    proposed_changes: list[CopilotChangeProposal] = Field(default_factory=list)
    model_name: str | None = None
    created_at: str


class CopilotQuestionRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=80)


class CopilotConversationSummary(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
