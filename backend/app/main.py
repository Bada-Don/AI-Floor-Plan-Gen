# main.py
from fastapi import FastAPI
from app.routes import layout
from fastapi.middleware.cors import CORSMiddleware # <--- Import CORS

app = FastAPI()

# --- Add CORS Middleware ---
origins = [
    "http://localhost:5173", # Default Vite dev server port
    "http://localhost:3000", # Default Create React App port
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -------------------------

app.include_router(layout.router)

@app.get("/health")
def health():
    return {"status": "ok"}