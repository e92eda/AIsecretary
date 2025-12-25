from __future__ import annotations
from pathlib import Path
import re

def grep_vault(vault_root: Path, query: str, limit: int = 30) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    pat = re.compile(re.escape(q), re.IGNORECASE)

    hits = []
    for md in vault_root.rglob("*.md"):
        if not md.is_file():
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if pat.search(line):
                hits.append({
                    "path": str(md.relative_to(vault_root)).replace("\\", "/"),
                    "line_no": idx,
                    "line": line.strip()
                })
                if len(hits) >= limit:
                    return hits
    return hits
