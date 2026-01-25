from fastapi import FastAPI
from app.api import contents
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(contents.router)

@app.get("/health")
async def health_check():
    return {"status": "up"}
