from fastapi import FastAPI

from app.routes import router

app = FastAPI(title="Release Captain", version="0.1.0")
app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "Release Captain", "docs": "/docs"}
