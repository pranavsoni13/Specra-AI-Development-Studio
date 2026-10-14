from app.core.traceability.requirements import RequirementRegistry

from .schemas import TestCase, TestSuite, TestSuiteDraft


class TestingQualityController:
    """Canonicalize requirement references and guarantee visible requirement coverage."""

    def validate(
        self,
        draft: TestSuiteDraft,
        registry: RequirementRegistry,
    ) -> TestSuite:
        requirements = {
            item.requirement_id: item
            for item in registry.requirements
        }
        cases: list[TestCase] = []
        warnings: list[str] = []
        covered: set[str] = set()

        for case in draft.test_cases:
            try:
                requirement = registry.resolve_reference(case.requirement_ref)
            except ValueError:
                warnings.append(
                    f"Discarded test '{case.title}' because its requirement reference "
                    f"could not be resolved: {case.requirement_ref[:120]}"
                )
                continue

            covered.add(requirement.requirement_id)
            cases.append(
                TestCase(
                    test_id=f"TC-{len(cases) + 1:03d}",
                    requirement_id=requirement.requirement_id,
                    requirement_text=requirement.text,
                    title=case.title.strip(),
                    test_type=case.test_type,
                    priority=case.priority,
                    objective=case.objective.strip(),
                    preconditions=[item.strip() for item in case.preconditions if item.strip()],
                    steps=[item.strip() for item in case.steps if item.strip()],
                    expected_result=case.expected_result.strip(),
                    generation_source="llm",
                    status="not_run",
                )
            )

        # A malformed/missing ID from the model must not silently leave a
        # functional requirement untestable. Add an explicit labelled fallback.
        for requirement_id, requirement in requirements.items():
            if requirement_id in covered:
                continue
            compact = requirement.text.strip()
            warnings.append(
                f"{requirement_id} has a deterministic coverage fallback because "
                "the model did not return a usable test for it."
            )
            cases.append(
                TestCase(
                    test_id=f"TC-{len(cases) + 1:03d}",
                    requirement_id=requirement_id,
                    requirement_text=compact,
                    title=f"Verify {requirement_id}: {compact[:110]}",
                    test_type="acceptance",
                    priority="P1",
                    objective=f"Verify that the system satisfies {requirement_id}.",
                    preconditions=[
                        "Use a test environment with the minimum setup and data needed by the requirement."
                    ],
                    steps=[
                        f"Arrange the preconditions required by this requirement: {compact}",
                        f"Perform the user/system interaction described by {requirement_id}.",
                        "Observe the resulting behavior and any persisted state relevant to the requirement.",
                    ],
                    expected_result=(
                        f"The observed behavior satisfies the stated requirement without "
                        f"introducing behavior outside its scope: {compact}"
                    ),
                    generation_source="template_fallback",
                    status="not_run",
                )
            )

        if not cases:
            raise ValueError("The test-design model did not return any usable cases.")

        if len(cases) > 100:
            warnings.append("The generated suite was capped at 100 cases.")
            cases = cases[:100]

        # IDs are contiguous and stable within a stored suite version, including
        # cases appended by fallback. Re-number after filtering/capping.
        cases = [
            case.model_copy(update={"test_id": f"TC-{index:03d}"})
            for index, case in enumerate(cases, start=1)
        ]

        return TestSuite(
            project_name=draft.project_name,
            summary=draft.summary.strip(),
            cases=cases,
            requirement_coverage=sorted(covered | {
                case.requirement_id for case in cases
            }),
            coverage_warnings=warnings,
        )
