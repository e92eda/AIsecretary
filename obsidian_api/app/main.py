from __future__ import annotations
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from urllib.parse import quote

from .config import settings
from .security import require_api_key
from .vault import safe_join, parse_frontmatter, extract_section, list_md_files
from .search import grep_vault
from .resolver import resolve_query
from .assistant_logic import handle_assistant_query

app = FastAPI(title="AIsecretary Obsidian Vault API", version="0.3.0")

origins = [o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

VAULT_ROOT = Path(settings.vault_root)
COMMANDS_FILE = Path(__file__).parent.parent / "commands.yml"

@app.get("/health")
def health():
    return {"ok": True, "vault_root": str(VAULT_ROOT)}

@app.get("/files", dependencies=[Depends(require_api_key)])
def files():
    if not VAULT_ROOT.exists():
        raise HTTPException(500, detail="VAULT_ROOT not found")
    return {"files": list_md_files(VAULT_ROOT)}

@app.get("/search", dependencies=[Depends(require_api_key)])
def search(q: str = Query(..., min_length=1), limit: int = 30):
    if not VAULT_ROOT.exists():
        raise HTTPException(500, detail="VAULT_ROOT not found")
    return {"q": q, "hits": grep_vault(VAULT_ROOT, q, limit=limit)}

@app.get("/note", dependencies=[Depends(require_api_key)])
def note(path: str = Query(..., description="Vault-relative path like Foo/Bar.md"),
         section: str | None = Query(default=None, description="Heading title to extract, exact match"),
         with_frontmatter: bool = True):
    if not VAULT_ROOT.exists():
        raise HTTPException(500, detail="VAULT_ROOT not found")
    try:
        p = safe_join(VAULT_ROOT, path)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    if not p.exists():
        raise HTTPException(404, detail="Note not found")

    text = p.read_text(encoding="utf-8", errors="ignore")
    fm, body = parse_frontmatter(text)
    out_text = text

    if section:
        sec = extract_section(body, section)
        if sec is None:
            raise HTTPException(404, detail=f"Section not found: {section}")
        out_text = sec

    resp = {"path": str(p.relative_to(VAULT_ROOT)).replace("\\", "/"), "text": out_text}
    if with_frontmatter:
        resp["frontmatter"] = fm
    return resp

@app.get("/resolve", dependencies=[Depends(require_api_key)])
def resolve_open_target(q: str = Query(..., min_length=1),
                        prefer: str = Query(default="most_hits")):
    r = resolve_query(query=q, vault_root=VAULT_ROOT, commands_file=COMMANDS_FILE, prefer=prefer)
    return r.model_dump()

def obsidian_open_url(vault_name: str, open_path: str, heading: str | None = None) -> str:
    if open_path.lower().endswith(".md"):
        open_path = open_path[:-3]
    file_enc = quote(open_path, safe="/")
    vault_enc = quote(vault_name, safe="")
    url = f"obsidian://open?vault={vault_enc}&file={file_enc}"
    if heading:
        url += "%23" + quote(heading, safe="")
    return url

@app.get("/open", dependencies=[Depends(require_api_key)])
def open_for_shortcuts(
    q: str = Query(..., min_length=1),
    vault: str = Query(..., min_length=1),
    prefer: str = Query(default="most_hits"),
    heading: str | None = Query(default=None),
):
    r = resolve_query(query=q, vault_root=VAULT_ROOT, commands_file=COMMANDS_FILE, prefer=prefer)
    if not r.found:
        return {"found": False, "obsidian_url": None, "reason": r.reason}

    url = obsidian_open_url(vault, r.open_path, heading=heading)
    return {"found": True, "source": r.source, "open_path": r.open_path, "obsidian_url": url, "candidates": r.candidates}

@app.get("/assistant", dependencies=[Depends(require_api_key)])
def assistant(
    q: str = Query(..., min_length=1, description="User query / voice command"),
    vault: str = Query(..., min_length=1, description="Mac側ObsidianのVault名（表示名）"),
    prefer: str = Query(default="most_hits"),
    heading: str | None = Query(default=None),
    section: str | None = Query(default=None),
):
    return handle_assistant_query(
        query=q,
        vault_name=vault,
        vault_root=VAULT_ROOT,
        commands_file=COMMANDS_FILE,
        obsidian_open_url_func=obsidian_open_url,
        prefer=prefer,
        heading=heading,
        section=section,
    )
