import os
from typing import Optional

# Load .env file if present (local development only — never commit .env to version control)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; fall back to system environment variables

class Settings:
    PROJECT_NAME: str = "TERRAIN ANALYZER"
    API_V1_STR: str = "/api"
    # API keys are loaded from environment variables ONLY.
    # Set OPENTOPOGRAPHY_API_KEY in your local .env file (see .env.example).
    # Never hardcode API keys in source code.
    OPENTOPOGRAPHY_API_KEY: str = os.getenv("OPENTOPOGRAPHY_API_KEY", "")
    OPENTOPOGRAPHY_API_URL: str = os.getenv("OPENTOPOGRAPHY_API_URL", "https://portal.opentopography.org/API/globaldem")
    OPENZENITH_API_URL: str = os.getenv("OPENZENITH_API_URL", "https://openzenith.cyopsys.com/api/elevation")
    STORAGE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")

settings = Settings()
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
