# FastAPI entrypoint
from fastapi import FastAPI
from app.routes import layout

app = FastAPI()
app.include_router(layout.router)

@app.get("/health")
def health():
    return {"status": "ok"}
