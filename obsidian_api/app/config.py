from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    vault_root: str = os.getenv("VAULT_ROOT", "/srv/obsidian/Vault")
    api_key: str = os.getenv("API_KEY", "")
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

settings = Settings()
