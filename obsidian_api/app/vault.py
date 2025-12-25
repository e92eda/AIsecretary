from __future__ import annotations
from pathlib import Path
import re
import yaml

def safe_join(root: Path, rel_path: str) -> Path:
    rel_path = rel_path.strip().lstrip("/").replace("\\", "/")
    p = (root / rel_path).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise ValueError("Path traversal detected")
    return p

def list_md_files(root: Path) -> list[str]:
    out = []
    for p in root.rglob("*.md"):
        if p.is_file():
            out.append(str(p.relative_to(root)).replace("\\", "/"))
    return out

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)

def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.search(text)
    if not m:
        return {}, text
    fm_raw = m.group(1)
    body = text[m.end():]
    try:
        data = yaml.safe_load(fm_raw) or {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    return data, body

def extract_section(markdown: str, heading: str) -> str | None:
    lines = markdown.splitlines()
    start_idx = None
    start_level = None
    pat = re.compile(r"^(#{1,6})\s+(.*)\s*$")
    for i, ln in enumerate(lines):
        m = pat.match(ln)
        if m and m.group(2) == heading:
            start_idx = i
            start_level = len(m.group(1))
            break
    if start_idx is None:
        return None

    buf = []
    for j in range(start_idx + 1, len(lines)):
        m = pat.match(lines[j])
        if m and len(m.group(1)) <= start_level:
            break
        buf.append(lines[j])
    return "\n".join(buf).strip()
