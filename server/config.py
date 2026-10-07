import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Environment-driven configuration; never credentials in source."""

    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/recruit")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "recruit")

    # Comma-separated list of origins allowed to call the API cross-origin.
    # Defaults to the Vite dev server; compose uses the proxy (single-origin).
    CORS_ORIGINS: list[str] = [
        origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    ]

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me-in-prod")
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))
    )
    REFRESH_TOKEN_EXPIRES_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "7"))
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))

    DEBUG: bool = os.getenv("FLASK_DEBUG", "1") == "1"
    VERSION: str = os.getenv("APP_VERSION", "0.1.0")
    SERVICE_NAME: str = "recruitment-api"

    # Whole-request cap (multipart overhead + payload). The strict per-field
    # rules are enforced in cv_service (5MB) and logo_service (1MB); this only
    # prevents unbounded bodies reaching them.
    MAX_CONTENT_LENGTH: int = 6 * 1024 * 1024