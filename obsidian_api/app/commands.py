from pathlib import Path
import yaml
from typing import List
from .models import Command

def load_commands(commands_file: Path) -> List[Command]:
    if not commands_file.exists():
        return []
    data = yaml.safe_load(commands_file.read_text(encoding="utf-8"))
    if not data:
        return []
    commands = []
    for item in data:
        try:
            commands.append(Command(**item))
        except Exception:
            continue
    return commands

def match_command(query: str, commands: List[Command]) -> Command | None:
    q = (query or "").lower()
    for cmd in commands:
        for kw in cmd.keywords:
            if kw.lower() in q:
                return cmd
    return None
