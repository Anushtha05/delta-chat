"""PyMongo client setup for MongoDB."""

from pymongo import MongoClient
from pymongo.database import Database

_client: MongoClient | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        from src.config import get_settings
        settings = get_settings()
        _client = MongoClient(settings.MONGO_URI)
    return _client


def get_db() -> Database:
    """Return the application MongoDB database instance."""
    from src.config import get_settings
    settings = get_settings()
    return _get_client()[settings.MONGO_DATABASE]
