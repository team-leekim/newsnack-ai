from fastapi import FastAPI
from app.api import contents

app = FastAPI(title="newsnack AI Server")

app.include_router(contents.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
