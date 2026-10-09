import tempfile
from pathlib import Path

from app.core.storage.project_store import ProjectStore


def main():
    with tempfile.TemporaryDirectory() as temp_dir:

        db_path = (
            Path(temp_dir)
            / "studio_test.db"
        )

        store = ProjectStore(
            db_path
        )

        project_id = (
            "test-project-001"
        )

        store.create_project(
            project_id=project_id,
            idea=(
                "Build a food delivery platform."
            ),
        )

        store.save_artifact(
            project_id,
            "requirements",
            {
                "project_name": "Food Delivery",
                "version_test": 1,
            },
            source="test",
        )

        store.save_artifact(
            project_id,
            "requirements",
            {
                "project_name": "Food Delivery",
                "version_test": 2,
            },
            instruction=(
                "Change the project name."
            ),
            source="test",
        )

        store.update_project(
            project_id,
            status="completed",
            project_name="Food Delivery",
            approved=True,
        )

        # Simulate backend restart by constructing
        # a completely new store instance.
        restarted_store = ProjectStore(
            db_path
        )

        project = (
            restarted_store.get_project(
                project_id
            )
        )

        assert project is not None

        assert project["status"] == (
            "completed"
        )

        assert project["approved"] is True

        assert project["project_name"] == (
            "Food Delivery"
        )

        assert project[
            "artifact_versions"
        ]["requirements"] == 2

        artifact = (
            restarted_store.get_latest_artifact(
                project_id,
                "requirements",
            )
        )

        assert artifact is not None

        assert artifact[
            "content"
        ]["version_test"] == 2

        versions = (
            restarted_store.get_artifact_versions(
                project_id,
                "requirements",
            )
        )

        assert len(versions) == 2

        print(
            "PROJECT STORE TEST: PASS"
        )

        print(
            f"Database: {db_path}"
        )

        print(
            "Persistence: PASS"
        )

        print(
            "Versioning: PASS"
        )


if __name__ == "__main__":
    main()