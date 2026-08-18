from pydantic import BaseModel, Field, field_validator


class RequirementAnalysis(BaseModel):
    project_name: str = Field(
        description="A neutral name based only on the user's idea. Never invent a brand name."
    )

    objective: str = Field(
        description="A concise statement of what the user wants the software to achieve."
    )

    user_roles: list[str] = Field(
        default_factory=list,
        description="User types explicitly mentioned or strongly implied by the idea."
    )

    functional_requirements: list[str] = Field(
        default_factory=list,
        description="Specific functions explicitly requested or directly implied by the user's idea."
    )

    non_functional_requirements: list[str] = Field(
        default_factory=list,
        description="Only quality requirements explicitly stated by the user."
    )

    constraints: list[str] = Field(
        default_factory=list,
        description="Only constraints explicitly stated by the user."
    )

    assumptions: list[str] = Field(
        default_factory=list,
        description="Reasonable interpretations made because information is missing."
    )

    risks: list[str] = Field(
        default_factory=list,
        description="Potential risks directly relevant to the stated project."
    )

    clarifications_needed: list[str] = Field(
        default_factory=list,
        description="Questions about information that is genuinely missing or ambiguous."
    )

    @field_validator("*", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            return " ".join(value.split())

        if isinstance(value, list):
            return [
                " ".join(item.split()) if isinstance(item, str) else item
                for item in value
            ]

        return value