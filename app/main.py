import logging
from fastapi import FastAPI
from app.api import contents
from app.core.config import settings

logging.basicConfig(level=logging.INFO, 
                    format='%(levelname)s: %(asctime)s - %(name)s - %(message)s',
                    datefmt='%H:%M:%S')

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(contents.router)

@app.get("/health")
async def health_check():
    return {"status": "up"}
