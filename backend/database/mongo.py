import os
import logging
from typing import Optional
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from pymongo.collection import Collection

logger = logging.getLogger(__name__)

_CLIENT: Optional[MongoClient] = None
_DB_NAME = "exam_grading_portal"
_USE_LIVE_PROXY: bool = False
LIVE_BASE_URL = os.environ.get("LIVE_API_URL", "https://final-year-project-rho-sable.vercel.app")
DEFAULT_MONGODB_URI = "mongodb+srv://shreyasspatil23:9scHnsn9sJd3fSNw@cluster0.dbplhay.mongodb.net/exam_grading_portal?retryWrites=true&w=majority&appName=Cluster0&authSource=admin"


def _clean_mongodb_uri(uri: str) -> str:
    """Sanitizes and fixes common MongoDB URI formatting issues (e.g., missing '?' delimiter)."""
    if not uri:
        return uri
    uri = uri.strip().strip('"').strip("'")
    
    # Fix missing '?' after database name, e.g. /exam_grading_portalretryWrites=true
    import re
    uri = re.sub(r'(/[^/?]+?)(retryWrites=|authSource=|appName=|w=|tls=)', r'\1?\2', uri)
    
    # Ensure authSource=admin is present
    if "authSource=" not in uri:
        sep = "&" if "?" in uri else "?"
        uri = f"{uri}{sep}authSource=admin"
        
    return uri


def is_live_proxy_active() -> bool:
    """Returns True if local direct MongoDB connection failed and live API proxy mode is active."""
    global _USE_LIVE_PROXY
    if _CLIENT is None and not _USE_LIVE_PROXY:
        try:
            get_mongo_client()
        except Exception:
            pass
    return _USE_LIVE_PROXY


def _load_env_mongodb_uri() -> str:
    """Reads MONGODB_URI from environment or local .env file, defaulting to MongoDB Atlas."""
    uri = os.environ.get("MONGODB_URI")
    if uri and uri.strip():
        return _clean_mongodb_uri(uri.strip())

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
                            return _clean_mongodb_uri(val)
        except Exception as e:
            logger.warning(f"Failed to read .env for MongoDB URI: {e}")

    # Default to MongoDB Atlas cluster
    return _clean_mongodb_uri(DEFAULT_MONGODB_URI)




def get_mongo_client() -> Optional[MongoClient]:
    """Returns a singleton MongoDB client connection with certifi CA bundle and local TLS fallback."""
    global _CLIENT, _USE_LIVE_PROXY
    if _CLIENT is not None:
        return _CLIENT

    uri = _load_env_mongodb_uri()
    try:
        import certifi
        ca = certifi.where()
    except ImportError:
        ca = None

    opts = {
        "serverSelectionTimeoutMS": 8000,
        "connectTimeoutMS": 8000,
        "socketTimeoutMS": 15000,
        "maxPoolSize": 30
    }
    if ca:
        opts["tlsCAFile"] = ca

    try:
        client = MongoClient(uri, **opts)
        client.admin.command('ping')
        logger.info("[MongoDB] Connected successfully to Atlas cluster!")
        _CLIENT = client
        _USE_LIVE_PROXY = False
        _init_indexes()
        return _CLIENT
    except Exception as primary_err:
        logger.warning(f"[MongoDB] Primary connection notice ({primary_err}), trying TLS fallback...")
        try:
            opts["tlsAllowInvalidCertificates"] = True
            opts["serverSelectionTimeoutMS"] = 8000
            client = MongoClient(uri, **opts)
            client.admin.command('ping')
            logger.info("[MongoDB] Connected successfully via TLS fallback!")
            _CLIENT = client
            _USE_LIVE_PROXY = False
            _init_indexes()
            return _CLIENT
        except Exception as e:
            logger.warning(f"[MongoDB] Direct MongoDB Atlas connection unavailable ({e}). Activating Live API Proxy Mode...")
            _CLIENT = None
            _USE_LIVE_PROXY = True
    return _CLIENT



def get_database() -> Optional[Database]:
    """Returns the primary database instance or None if unreachable."""
    client = get_mongo_client()
    if client is None:
        return None
    try:
        return client[_DB_NAME]
    except Exception:
        return None


def get_classrooms_collection() -> Optional[Collection]:
    """Returns the classrooms collection or None if database is unreachable."""
    db = get_database()
    if db is None:
        return None
    try:
        return db["classrooms"]
    except Exception:
        return None


def get_submissions_collection() -> Optional[Collection]:
    """Returns the student submissions collection or None if database is unreachable."""
    db = get_database()
    if db is None:
        return None
    try:
        return db["submissions"]
    except Exception:
        return None



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
