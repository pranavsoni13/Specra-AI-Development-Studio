from app.agents.project_planner.agent import ProjectPlanner
from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.software_architect.agent import SoftwareArchitect
from app.agents.technical_reviewer.agent import TechnicalReviewer


def main():
    idea = """
    I want to build a college learning management system where
    students can view courses, access study materials, submit
    assignments, see their grades, and receive notifications.
    Teachers should be able to upload course materials, create
    assignments, grade submissions, and post announcements.
    """

    requirement_agent = RequirementAnalyst()
    planner_agent = ProjectPlanner()
    architect_agent = SoftwareArchitect()
    reviewer_agent = TechnicalReviewer()

    print("\n=== STEP 1: REQUIREMENTS ===\n")
    requirements = requirement_agent.analyze(idea)
    print(
        requirements.model_dump_json(indent=2)
    )

    print("\n=== STEP 2: PROJECT PLAN ===\n")
    project_plan = planner_agent.plan(
        requirements
    )
    print(
        project_plan.model_dump_json(indent=2)
    )

    print("\n=== STEP 3: ARCHITECTURE ===\n")
    architecture = architect_agent.design(
        requirements,
        project_plan,
    )
    print(
        architecture.model_dump_json(indent=2)
    )

    print("\n=== STEP 4: TECHNICAL REVIEW ===\n")
    review = reviewer_agent.review(
        requirements,
        project_plan,
        architecture,
    )
    print(
        review.model_dump_json(indent=2)
    )


if __name__ == "__main__":
    main()