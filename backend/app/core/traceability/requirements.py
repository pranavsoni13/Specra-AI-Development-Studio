from dataclasses import dataclass
from typing import Protocol


class RequirementSource(Protocol):
    """
    Minimal interface required by the traceability layer.

    This keeps the core traceability module independent from the
    Requirement Analyst agent implementation.
    """

    functional_requirements: list[str]


@dataclass(frozen=True)
class FunctionalRequirement:
    """
    Canonical representation of one functional requirement.
    """

    requirement_id: str
    text: str


class RequirementRegistry:
    """
    Canonical registry for functional requirements.

    The registry gives every functional requirement a deterministic,
    human-readable ID such as FR-001, FR-002, etc.

    It also resolves legacy/exact-text references so existing artifacts
    can transition to ID-based traceability safely.
    """

    def __init__(
        self,
        requirements: list[FunctionalRequirement],
    ):
        if not requirements:
            raise ValueError(
                "Requirement registry must contain at least one "
                "functional requirement."
            )

        self._requirements = tuple(requirements)

        self._by_id = {
            requirement.requirement_id.casefold(): requirement
            for requirement in self._requirements
        }

        self._by_text = {
            self._normalize_text(requirement.text): requirement
            for requirement in self._requirements
        }

    @classmethod
    def from_analysis(
        cls,
        analysis: RequirementSource,
    ) -> "RequirementRegistry":
        """
        Build a registry from a validated RequirementAnalysis artifact.

        Requirement IDs are assigned in the order of the validated
        functional_requirements list.
        """
        functional_requirements = [
            requirement.strip()
            for requirement in analysis.functional_requirements
            if isinstance(requirement, str)
            and requirement.strip()
        ]

        if not functional_requirements:
            raise ValueError(
                "RequirementAnalysis contains no functional requirements."
            )

        requirements = [
            FunctionalRequirement(
                requirement_id=f"FR-{index:03d}",
                text=requirement,
            )
            for index, requirement in enumerate(
                functional_requirements,
                start=1,
            )
        ]

        return cls(requirements)

    @property
    def requirements(self) -> tuple[FunctionalRequirement, ...]:
        """
        Return all canonical functional requirements in order.
        """
        return self._requirements

    @property
    def ids(self) -> tuple[str, ...]:
        """
        Return all canonical requirement IDs in order.
        """
        return tuple(
            requirement.requirement_id
            for requirement in self._requirements
        )

    def get(
        self,
        requirement_id: str,
    ) -> FunctionalRequirement:
        """
        Return a requirement by canonical ID.
        """
        normalized_id = requirement_id.strip().casefold()

        requirement = self._by_id.get(
            normalized_id
        )

        if requirement is None:
            raise ValueError(
                f"Unknown functional requirement ID: "
                f"{requirement_id}"
            )

        return requirement

    def resolve_reference(
        self,
        reference: str,
    ) -> FunctionalRequirement:
        """
        Resolve either:

        1. a canonical ID such as FR-001
        2. the exact functional requirement text

        This allows the system to remain compatible with older
        agent outputs while transitioning to ID-based references.
        """
        if not isinstance(reference, str):
            raise ValueError(
                "Requirement reference must be a string."
            )

        cleaned_reference = reference.strip()

        if not cleaned_reference:
            raise ValueError(
                "Requirement reference cannot be empty."
            )

        by_id = self._by_id.get(
            cleaned_reference.casefold()
        )

        if by_id is not None:
            return by_id

        normalized_text = self._normalize_text(
            cleaned_reference
        )

        by_text = self._by_text.get(
            normalized_text
        )

        if by_text is not None:
            return by_text

        raise ValueError(
            "Unknown functional requirement reference: "
            f"{reference}"
        )

    def normalize_reference(
        self,
        reference: str,
    ) -> str:
        """
        Convert an ID or exact requirement text into its canonical ID.
        """
        return self.resolve_reference(
            reference
        ).requirement_id

    def normalize_references(
        self,
        references: list[str],
    ) -> list[str]:
        """
        Convert all references into canonical IDs while preserving order
        and removing duplicates.
        """
        normalized: list[str] = []
        seen: set[str] = set()

        for reference in references:
            requirement_id = self.normalize_reference(
                reference
            )

            if requirement_id in seen:
                continue

            seen.add(requirement_id)
            normalized.append(requirement_id)

        return normalized

    def validate_references(
        self,
        references: list[str],
    ) -> None:
        """
        Validate that every supplied reference resolves to a known
        functional requirement.
        """
        for reference in references:
            self.resolve_reference(
                reference
            )

    def text_for_id(
        self,
        requirement_id: str,
    ) -> str:
        """
        Return the original requirement text for a canonical ID.
        """
        return self.get(
            requirement_id
        ).text

    def to_prompt_text(self) -> str:
        """
        Build a compact representation suitable for LLM prompts.
        """
        lines = [
            "FUNCTIONAL REQUIREMENTS",
            "------------------------",
        ]

        for requirement in self._requirements:
            lines.append(
                f"{requirement.requirement_id}: "
                f"{requirement.text}"
            )

        lines.extend(
            [
                "",
                "REFERENCE RULE",
                "--------------",
                "Use only canonical requirement IDs "
                "(for example FR-001).",
                "Do not invent requirement IDs.",
            ]
        )

        return "\n".join(lines)

    def as_mapping(self) -> dict[str, str]:
        """
        Return a simple ID -> requirement text mapping.
        """
        return {
            requirement.requirement_id: requirement.text
            for requirement in self._requirements
        }

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        """
        Normalize only whitespace/case for reference matching.

        No semantic rewriting is performed.
        """
        return " ".join(
            value.split()
        ).casefold()