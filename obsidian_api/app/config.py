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

    # HTML display settings
    css_theme: str = os.getenv("CSS_THEME", "obsidian")  # light|dark|obsidian|minimal
    mobile_optimized: bool = os.getenv("MOBILE_OPTIMIZED", "true").lower() == "true"
    html_font_size: str = os.getenv("HTML_FONT_SIZE", "16px")
    html_max_width: str = os.getenv("HTML_MAX_WIDTH", "800px")
    
    # Markdown save settings
    vault_write_root: str = os.getenv("VAULT_WRITE_ROOT", "Inbox")  # Restrict saves to subdirectory for safety


settings = Settings()
