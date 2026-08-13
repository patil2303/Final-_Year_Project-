import os
import logging
from typing import Optional
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from pymongo.collection import Collection

logger = logging.getLogger(__name__)

_CLIENT: Optional[MongoClient] = None
_DB_NAME = "exam_grading_portal"


def _load_env_mongodb_uri() -> str:
    """Reads MONGODB_URI from environment or local .env file."""
    uri = os.environ.get("MONGODB_URI")
    if uri:
        return uri

    # Try loading from .env in project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("MONGODB_URI="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception as e:
            logger.warning(f"Failed to read .env for MongoDB URI: {e}")

    # Fallback to local MongoDB
    return "mongodb://localhost:27017"


def get_mongo_client() -> MongoClient:
    """Returns a singleton MongoDB client connection."""
    global _CLIENT
    if _CLIENT is None:
        uri = _load_env_mongodb_uri()
        _CLIENT = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
            maxPoolSize=50
        )
        try:
            _CLIENT.admin.command('ping')
            logger.info("[MongoDB] Connected successfully to cluster!")
            _init_indexes()
        except Exception as e:
            logger.error(f"[MongoDB] Connection healthcheck failed: {e}")
            raise
    return _CLIENT


def get_database() -> Database:
    """Returns the primary database instance."""
    client = get_mongo_client()
    return client[_DB_NAME]


def get_classrooms_collection() -> Collection:
    """Returns the classrooms collection."""
    return get_database()["classrooms"]


def get_submissions_collection() -> Collection:
    """Returns the student submissions collection."""
    return get_database()["submissions"]


def _init_indexes():
    """Initializes efficient sorting and unique indexes on MongoDB collections."""
    try:
        db = get_database()
        
        # Classroom indexes
        db["classrooms"].create_index([("classroom_id", ASCENDING)], unique=True)
        
        # Submission indexes: compound unique index to prevent duplicates per class
        db["submissions"].create_index(
            [("classroom_id", ASCENDING), ("prn", ASCENDING)],
            unique=True,
            sparse=True
        )
        
        # Natural sorting index for instant roster retrieval
        db["submissions"].create_index([("classroom_id", ASCENDING), ("roll_numeric", ASCENDING)])
        db["submissions"].create_index([("classroom_id", ASCENDING), ("submitted_at", ASCENDING)])
        
        logger.info("[MongoDB] Database collections and performance indexes initialized.")
    except Exception as e:
        logger.warning(f"[MongoDB] Index creation notice: {e}")
