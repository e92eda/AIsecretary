from pathlib import Path
from .commands import load_commands, match_command
from .search import grep_vault
from .models import ResolveResult

def resolve_query(query: str, vault_root: Path, commands_file: Path, prefer: str = "most_hits") -> ResolveResult:
    commands = load_commands(commands_file)
    cmd = match_command(query, commands)
    if cmd:
        return ResolveResult(found=True, open_path=cmd.open.path, source="command")

    hits = grep_vault(vault_root, query, limit=200)
    if not hits:
        return ResolveResult(found=False, reason="no hits")

    counts = {}
    for h in hits:
        counts[h["path"]] = counts.get(h["path"], 0) + 1

    candidates = list(counts.items())
    if prefer == "shortest":
        candidates.sort(key=lambda x: (len(x[0]), -x[1]))
    else:
        candidates.sort(key=lambda x: (-x[1], len(x[0])))

    return ResolveResult(found=True, open_path=candidates[0][0], source="search", candidates=candidates[:10])
