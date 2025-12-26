from __future__ import annotations
from pathlib import Path
import re

def grep_vault(vault_root: Path, query: str, limit: int = 30) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    
    hits = []
    
    # 1) ファイル名検索を追加
    for md in vault_root.rglob("*.md"):
        if not md.is_file():
            continue
        rel_path = str(md.relative_to(vault_root)).replace("\\", "/")
        if q.lower() in rel_path.lower():
            hits.append({
                "path": rel_path,
                "line_no": 0,  # ファイル名マッチを示す
                "line": f"[FileName Match: {rel_path}]"
            })
            if len(hits) >= limit:
                return hits
    
    # 2) 既存の内容検索
    pat = re.compile(re.escape(q), re.IGNORECASE)
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
