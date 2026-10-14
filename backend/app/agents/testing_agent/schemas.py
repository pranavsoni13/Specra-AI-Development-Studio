from typing import Literal

from pydantic import BaseModel, Field


TestType = Literal[
    "unit",
    "integration",
    "acceptance",
    "negative",
    "security",
    "accessibility",
    "performance",
]
Priority = Literal["P0", "P1", "P2", "P3"]
TestStatus = Literal["not_run", "passed", "failed", "blocked"]


class TestCaseDraft(BaseModel):
    """One proposed test returned by the language model."""

    requirement_ref: str = Field(
        min_length=1,
        description="A canonical functional requirement ID like FR-001, or the exact requirement text.",
    )
    title: str = Field(min_length=3, max_length=180)
    test_type: TestType
    priority: Priority
    objective: str = Field(min_length=5, max_length=1200)
    preconditions: list[str] = Field(default_factory=list, max_length=12)
    steps: list[str] = Field(min_length=1, max_length=16)
    expected_result: str = Field(min_length=5, max_length=1800)


class TestSuiteDraft(BaseModel):
    project_name: str = Field(min_length=1, max_length=180)
    summary: str = Field(min_length=5, max_length=2400)
    test_cases: list[TestCaseDraft] = Field(min_length=1, max_length=100)


class TestCase(BaseModel):
    test_id: str
    requirement_id: str
    requirement_text: str
    title: str
    test_type: TestType
    priority: Priority
    objective: str
    preconditions: list[str]
    steps: list[str]
    expected_result: str
    generation_source: Literal["llm", "template_fallback"]
    status: TestStatus = "not_run"
    execution_notes: str | None = None
    environment: str | None = None
    executed_at: str | None = None
    executed_by: str | None = None


class TestSuite(BaseModel):
    project_name: str
    summary: str
    cases: list[TestCase]
    requirement_coverage: list[str]
    coverage_warnings: list[str] = Field(default_factory=list)


class TestResultUpdate(BaseModel):
    status: Literal["not_run", "passed", "failed", "blocked"]
    execution_notes: str | None = Field(default=None, max_length=5000)
    environment: str | None = Field(default=None, max_length=500)
