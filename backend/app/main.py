from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .llm_client import llm_enabled
from .models import Health
from .routers import plan, resources
from .store import store

app = FastAPI(title="AidGraph API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https?://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(plan.router)
app.include_router(resources.router)


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(ok=True, llm=llm_enabled(), resources=len(store.resources))
