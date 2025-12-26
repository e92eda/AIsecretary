from __future__ import annotations

import os
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables from .env (if present)
load_dotenv()


class Settings(BaseModel):
    # Obsidian vault root directory
    vault_root: str = os.getenv("VAULT_ROOT", "/srv/obsidian/Vault")

    # API key for this FastAPI server (sent via X-API-Key header)
    api_key: str = os.getenv("AISECRETARY_API_KEY", "")

    # CORS origins (comma-separated or "*")
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")


settings = Settings()
