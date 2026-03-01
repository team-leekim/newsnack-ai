from fastapi import FastAPI, Security

from app.api import contents, debug
from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.logging import setup_logging
from app.core.security import verify_api_key

setup_logging()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(contents.router, dependencies=[Security(verify_api_key)])
app.include_router(debug.router, dependencies=[Security(verify_api_key)])

@app.get("/health")
async def health_check():
    return {"status": "UP"}
