from app.workflows.project_workflow import project_workflow


def main():
    idea = """
    I want to build an online food delivery platform where
    customers can discover restaurants, browse menus,
    place orders, make payments, and track deliveries.
    """

    result = project_workflow.invoke(
        {
            "idea": idea,
        }
    )

    print("\n=== REQUIREMENTS ===\n")
    print(
        result["requirements"].model_dump_json(indent=2)
    )

    print("\n=== PROJECT PLAN ===\n")
    print(
        result["project_plan"].model_dump_json(indent=2)
    )

    print("\n=== SYSTEM ARCHITECTURE ===\n")
    print(
        result["architecture"].model_dump_json(indent=2)
    )

    print("\n=== TECHNICAL REVIEW ===\n")
    print(
        result["review"].model_dump_json(indent=2)
    )


if __name__ == "__main__":
    main()