from pydantic import BaseModel
from typing import List, Optional

class CommandOpen(BaseModel):
    path: str

class Command(BaseModel):
    name: str
    keywords: List[str]
    open: CommandOpen

class ResolveResult(BaseModel):
    found: bool
    reason: Optional[str] = None
    open_path: Optional[str] = None
    source: Optional[str] = None  # "command" | "search"
    candidates: Optional[list] = None
