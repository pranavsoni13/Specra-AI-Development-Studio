"""Fast deterministic tests for the LangGraph orchestration layer.

No local model or API credential is required.
Run from backend/:
    python test_langgraph_workflow.py
"""
import unittest

from app.workflows.project_workflow import ProjectWorkflow


class FakeArtifact:
    def __init__(self, name, **fields):
        self.project_name = name
        self.fields = fields

    def model_dump(self):
        return {"project_name": self.project_name, **self.fields}


class FakeReview(FakeArtifact):
    def __init__(self, name, status="PASS"):
        super().__init__(name, overall_status=status)
        self.overall_status = status


class FakeRequirementsAgent:
    def __init__(self, calls):
        self.calls = calls

    def analyze(self, idea, project_context=None):
        self.calls.append(("requirements", idea, project_context))
        return FakeArtifact("Test Project", objective="test")


class FakePlannerAgent:
    def __init__(self, calls):
        self.calls = calls

    def plan(self, requirements):
        self.calls.append(("project_plan", requirements.project_name))
        return FakeArtifact("Test Project", milestones=[])


class FakeArchitectAgent:
    def __init__(self, calls, fail=False):
        self.calls = calls
        self.fail = fail

    def design(self, requirements, plan):
        self.calls.append(("architecture", requirements.project_name, plan.project_name))
        if self.fail:
            raise RuntimeError("simulated architecture failure")
        return FakeArtifact("Test Project", architecture_style="Modular Monolith")


class FakeReviewerAgent:
    def __init__(self, calls):
        self.calls = calls

    def review(self, requirements, plan, architecture):
        self.calls.append(("technical_review", architecture.project_name))
        return FakeReview("Test Project", status="PASS")


class LangGraphWorkflowTests(unittest.TestCase):
    def _workflow(self, fail_architect=False):
        workflow = ProjectWorkflow()
        calls = []
        workflow.requirement_agent = FakeRequirementsAgent(calls)
        workflow.planner_agent = FakePlannerAgent(calls)
        workflow.architect_agent = FakeArchitectAgent(calls, fail=fail_architect)
        workflow.reviewer_agent = FakeReviewerAgent(calls)
        return workflow, calls

    def test_nodes_run_in_existing_order_and_preserve_callbacks(self):
        workflow, calls = self._workflow()
        stages = []
        artifacts = []

        result = workflow.run(
            "  Build a test project  ",
            project_context="A saved decision",
            on_stage=lambda stage, status: stages.append((stage, status)),
            on_artifact=lambda stage, artifact: artifacts.append(
                (stage, artifact.project_name)
            ),
        )

        self.assertEqual(
            [call[0] for call in calls],
            ["requirements", "project_plan", "architecture", "technical_review"],
        )
        self.assertEqual(calls[0], ("requirements", "Build a test project", "A saved decision"))
        self.assertTrue(result.approved)
        self.assertEqual(
            artifacts,
            [
                ("requirements", "Test Project"),
                ("project_plan", "Test Project"),
                ("architecture", "Test Project"),
                ("technical_review", "Test Project"),
            ],
        )
        self.assertEqual(
            stages,
            [
                ("requirements", "running"),
                ("requirements", "completed"),
                ("project_plan", "running"),
                ("project_plan", "completed"),
                ("architecture", "running"),
                ("architecture", "completed"),
                ("technical_review", "running"),
                ("technical_review", "completed"),
            ],
        )

    def test_failed_node_emits_failed_status_and_stops_downstream_nodes(self):
        workflow, calls = self._workflow(fail_architect=True)
        stages = []

        with self.assertRaisesRegex(RuntimeError, "simulated architecture failure"):
            workflow.run(
                "Build a test project",
                on_stage=lambda stage, status: stages.append((stage, status)),
            )

        self.assertEqual(
            [call[0] for call in calls],
            ["requirements", "project_plan", "architecture"],
        )
        self.assertEqual(stages[-2:], [
            ("architecture", "running"),
            ("architecture", "failed"),
        ])

    def test_blank_idea_is_rejected_before_running_graph(self):
        workflow, calls = self._workflow()
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            workflow.run("   ")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
