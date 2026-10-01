from fastapi import FastAPI

from app.api.routes.planner import router as planner_router
from app.api.routes.projects import router as projects_router
from app.api.routes.requirements import router as requirements_router


app = FastAPI(
    title="AI Development Studio",
    description=(
        "Multi-Agent AI Software Engineering Platform "
        "for transforming software ideas into validated "
        "engineering artifacts."
    ),
    version="0.2.0",
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


@app.get(
    "/",
    tags=["System"],
)
async def root():
    return {
        "name": "AI Development Studio",
        "version": "0.2.0",
        "status": "running",
    }


@app.get(
    "/health",
    tags=["System"],
)
async def health():
    return {
        "status": "healthy",
    }