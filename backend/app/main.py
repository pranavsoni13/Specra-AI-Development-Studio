from fastapi import FastAPI

from app.api.routes.requirements import router as requirements_router


app = FastAPI(
    title="AI Development Studio",
    description="Multi-Agent AI Software Engineering Platform",
    version="0.1.0",
)


app.include_router(requirements_router)


@app.get("/")
async def root():
    return {
        "name": "AI Development Studio",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }