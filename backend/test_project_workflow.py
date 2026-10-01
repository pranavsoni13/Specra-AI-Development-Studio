from app.workflows.project_workflow import ProjectWorkflow


def main():
    idea = (
        "Build an online food delivery platform where customers "
        "can discover restaurants, browse menus, place orders, "
        "make payments, and track deliveries."
    )

    workflow = ProjectWorkflow()

    result = workflow.run(idea)

    print("\n=== FINAL WORKFLOW RESULT ===\n")

    print(
        result.requirements.model_dump_json(
            indent=2
        )
    )

    print("\n=== PROJECT PLAN ===\n")

    print(
        result.project_plan.model_dump_json(
            indent=2
        )
    )

    print("\n=== SYSTEM ARCHITECTURE ===\n")

    print(
        result.architecture.model_dump_json(
            indent=2
        )
    )

    print("\n=== TECHNICAL REVIEW ===\n")

    print(
        result.review.model_dump_json(
            indent=2
        )
    )

    print(
        f"\n=== APPROVED: {result.approved} ==="
    )


if __name__ == "__main__":
    main()