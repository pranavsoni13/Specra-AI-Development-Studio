from typing import Literal

from pydantic import BaseModel, Field


class GeneratedFileDraft(BaseModel):
    path: str = Field(min_length=1, max_length=240)
    purpose: str = Field(default="", max_length=500)
    content: str = Field(max_length=30000)


class CodeBundleDraft(BaseModel):
    """Untrusted model output; paths and source are validated before persistence."""

    project_name: str = Field(min_length=1, max_length=180)
    summary: str = Field(min_length=5, max_length=2400)
    files: list[GeneratedFileDraft] = Field(default_factory=list, max_length=35)
    setup_notes: list[str] = Field(default_factory=list, max_length=24)
    test_notes: list[str] = Field(default_factory=list, max_length=24)


class CodeFile(BaseModel):
    path: str
    purpose: str
    content: str


class CodeBundle(BaseModel):
    project_name: str
    summary: str
    stack: Literal["fastapi-react"] = "fastapi-react"
    files: list[CodeFile]
    setup_notes: list[str]
    test_notes: list[str]
    validation_warnings: list[str] = Field(default_factory=list)
    validation_status: Literal["static_checks_clear", "needs_review"] = "needs_review"
    execution_status: Literal["not_executed"] = "not_executed"
    generation_source: Literal["llm_plus_scaffold"] = "llm_plus_scaffold"
