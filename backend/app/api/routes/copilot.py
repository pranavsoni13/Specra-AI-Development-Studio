import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.agents.project_copilot.agent import ProjectCopilotAgent
from app.agents.project_copilot.schemas import CopilotQuestionRequest
from app.core.context_store import project_context_store
from app.core.copilot_store import copilot_store
from app.core.security import auth_store, get_current_user, require_project_roles
from app.core.storage.project_store import project_store


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/copilot",
    tags=["Specra AI Copilot"],
    dependencies=[Depends(get_current_user)],
)


def _project_or_404(project_id: str) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.get("")
def list_conversations(
    project_id: str,
    user: dict = Depends(get_current_user),
    _: dict = Depends(require_project_roles()),
) -> dict:
    _project_or_404(project_id)
    project_role = auth_store.get_project_role(project_id, user)
    return {
        "conversations": copilot_store.list_conversations(
            project_id=project_id,
            user_id=user["user_id"],
        ),
        "my_role": project_role,
        "can_ask": project_role in {
            "admin", "owner", "analyst", "planner", "architect",
            "tester", "reviewer", "developer",
        },
    }


@router.get("/{conversation_id}")
def get_conversation(
    project_id: str,
    conversation_id: str,
    user: dict = Depends(get_current_user),
    _: dict = Depends(require_project_roles()),
) -> dict:
    _project_or_404(project_id)
    conversation = copilot_store.get_conversation(
        project_id=project_id,
        user_id=user["user_id"],
        conversation_id=conversation_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"conversation": conversation}


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    project_id: str,
    conversation_id: str,
    user: dict = Depends(get_current_user),
    _: dict = Depends(require_project_roles()),
) -> Response:
    _project_or_404(project_id)
    deleted = copilot_store.delete_conversation(
        project_id=project_id,
        user_id=user["user_id"],
        conversation_id=conversation_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ask", status_code=status.HTTP_201_CREATED)
def ask_copilot(
    project_id: str,
    request: CopilotQuestionRequest,
    user: dict = Depends(get_current_user),
    _: dict = Depends(
        require_project_roles(
            "analyst",
            "planner",
            "architect",
            "tester",
            "reviewer",
            "developer",
        )
    ),
) -> dict:
    project = _project_or_404(project_id)
    question = request.message.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    existing_conversation = None
    history: list[dict] = []
    if request.conversation_id:
        existing_conversation = copilot_store.get_conversation(
            project_id=project_id,
            user_id=user["user_id"],
            conversation_id=request.conversation_id,
        )
        if existing_conversation is None:
            # Conversations are private to the creating user even when the
            # underlying project is shared with other members.
            raise HTTPException(status_code=404, detail="Conversation not found.")
        history = existing_conversation["messages"]

    artifacts = project_store.get_artifacts(project_id)
    versions = project_store.get_latest_version_numbers(project_id)
    context_records = project_context_store.list_context(project_id)

    try:
        agent = ProjectCopilotAgent()
        answer = agent.answer(
            project=project,
            artifacts=artifacts,
            versions=versions,
            context_records=context_records,
            history=history,
            question=question,
        )
    except Exception as exc:
        logger.exception(
            "Copilot response failed for project %s (%s)",
            project_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Specra Copilot could not answer with the configured model. Check provider availability and try again.",
        ) from exc

    conversation = existing_conversation
    if conversation is None:
        conversation = copilot_store.create_conversation(
            project_id=project_id,
            user_id=user["user_id"],
            first_question=question,
        )

    saved = copilot_store.append_exchange(
        conversation_id=conversation["conversation_id"],
        project_id=project_id,
        user_id=user["user_id"],
        question=question,
        answer=answer,
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="Conversation is no longer available.")

    return {
        "conversation": saved,
        "answer": saved["messages"][-1],
        "project_sources_available": len(agent.build_sources(
            artifacts,
            versions,
            context_records,
        )),
    }
