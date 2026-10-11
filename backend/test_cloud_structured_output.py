import os
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from app.core.llm.client import LocalLLMClient


class ExampleArtifact(BaseModel):
    project_name: str
    milestones: list[str]


def _fake_response(content: str):
    return SimpleNamespace(
        message=SimpleNamespace(content=content),
        prompt_eval_count=10,
        eval_count=8,
        prompt_eval_duration=1_000_000,
        eval_duration=2_000_000,
        total_duration=3_000_000,
    )


def test_ollama_cloud_uses_prompt_schema_and_extracts_json():
    response = _fake_response(
        'Result follows:\n'
        '{"project_name":"Specra demo","milestones":["Plan","Build"]}'
    )

    with patch.dict(
        os.environ,
        {
            "OLLAMA_HOST": "https://ollama.com",
            "OLLAMA_API_KEY": "test-key",
        },
        clear=False,
    ):
        with patch("app.core.llm.client.ollama.Client") as client_factory:
            fake_client = client_factory.return_value
            fake_client.chat.return_value = response
            client = LocalLLMClient(debug=False)

            artifact = client.generate_structured(
                system_prompt="Return a project artifact.",
                user_prompt="Create a small demo plan.",
                output_schema=ExampleArtifact,
            )

            call = fake_client.chat.call_args
            assert "format" not in call.kwargs
            assert "OUTPUT JSON SCHEMA" in call.kwargs["messages"][1]["content"]
            client_factory.assert_called_once_with(
                host="https://ollama.com",
                headers={"Authorization": "Bearer test-key"},
            )
            assert artifact.project_name == "Specra demo"
            assert artifact.milestones == ["Plan", "Build"]


def test_local_ollama_keeps_native_json_schema_mode():
    response = _fake_response(
        '{"project_name":"Local demo","milestones":["Test"]}'
    )

    with patch.dict(os.environ, {"OLLAMA_HOST": ""}, clear=False):
        with patch("app.core.llm.client.ollama.Client") as client_factory:
            fake_client = client_factory.return_value
            fake_client.chat.return_value = response
            client = LocalLLMClient(debug=False)

            artifact = client.generate_structured(
                system_prompt="Return a project artifact.",
                user_prompt="Create a local plan.",
                output_schema=ExampleArtifact,
            )

            call = fake_client.chat.call_args
            assert call.kwargs["format"] == ExampleArtifact.model_json_schema()
            assert artifact.project_name == "Local demo"
