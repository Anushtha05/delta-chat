"""Delta Chat — FastAPI application entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from sqlalchemy import text, create_engine

# Allow startup without OPENROUTER_API_KEY for health-check-only containers
os.environ.setdefault("TESTING", "true")

from src.config import get_settings
from src.observability.logging import setup_logging

# Configure structured JSON logging before anything else logs
setup_logging()

from src.api.ingest import router as ingest_router
from src.api.compare import router as compare_router
from src.api.chat import router as chat_router
from src.api.metrics import router as metrics_router

settings = get_settings()

app = FastAPI(title="Delta Chat API", version="0.1.0")

# CORS — allow frontend to call backend across origins in dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

# Register API routers
app.include_router(ingest_router)
app.include_router(compare_router)
app.include_router(chat_router)
app.include_router(metrics_router)


@app.get("/health")
def health_check():
    """Check MySQL and MongoDB connectivity and return status."""
    mysql_ok = False
    mongo_ok = False

    # Check MySQL
    try:
        engine = create_engine(settings.mysql_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        mysql_ok = True
    except Exception:
        pass

    # Check MongoDB
    try:
        client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        mongo_ok = True
    except Exception:
        pass

    return {"status": "ok", "mysql": mysql_ok, "mongo": mongo_ok}
