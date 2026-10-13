from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.testing import router as testing_router
from app.api.routes.documents import router as documents_router
from app.api.routes.copilot import router as copilot_router
from app.api.routes.code_generation import router as code_generation_router
from app.api.routes.context import router as context_router
from app.api.routes.planner import router as planner_router
from app.api.routes.projects import router as projects_router
from app.api.routes.requirements import router as requirements_router


app = FastAPI(
    title="Specra",
    description=(
        "AI Software Engineering Studio"
    ),
    version="0.1.0",
)


app.include_router(
    auth_router
)

app.include_router(
    testing_router
)

app.include_router(
    documents_router
)

app.include_router(
    copilot_router
)

app.include_router(
    code_generation_router
)

app.include_router(
    requirements_router
)

app.include_router(
    planner_router
)

app.include_router(
    projects_router
)

app.include_router(
    context_router
)


@app.get("/")
async def root():
    return {
        "name": "Specra",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }
