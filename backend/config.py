import os
from typing import Optional

class Settings:
    PROJECT_NAME: str = "TERRAIN ANALYZER"
    API_V1_STR: str = "/api"
    OPENTOPOGRAPHY_API_KEY: Optional[str] = os.getenv("OPENTOPOGRAPHY_API_KEY", "")
    OPENZENITH_API_URL: str = os.getenv("OPENZENITH_API_URL", "https://openzenith.cyopsys.com/api/elevation")
    STORAGE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")

settings = Settings()
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
