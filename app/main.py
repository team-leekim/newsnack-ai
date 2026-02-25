import logging
from fastapi import FastAPI, Security

from app.api import contents, debug
from app.core.config import settings
from app.core.security import verify_api_key

logging.basicConfig(level=logging.INFO, 
                    format='%(levelname)s: %(asctime)s - %(name)s - %(message)s',
                    datefmt='%H:%M:%S')

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(contents.router, dependencies=[Security(verify_api_key)])
app.include_router(debug.router, dependencies=[Security(verify_api_key)])

@app.get("/health")
async def health_check():
    return {"status": "UP"}
