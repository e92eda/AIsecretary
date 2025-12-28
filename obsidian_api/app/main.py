from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from datetime import datetime
from dataclasses import dataclass

from fastapi import FastAPI, Depends, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .security import require_api_key
from .vault import safe_join, parse_frontmatter, extract_section, list_md_files
from .search import grep_vault
from .resolver import resolve_query
from .assistant_logic import handle_assistant_query


app = FastAPI(title="AIsecretary Obsidian Vault API", version="0.3.0")

origins = (
    [o.strip() for o in settings.cors_origins.split(",")]
    if getattr(settings, "cors_origins", None)
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

VAULT_ROOT = Path(settings.vault_root)
COMMANDS_FILE = Path(__file__).parent.parent / "commands.yml"


@dataclass(frozen=True)
class AssistantOrchestrator:
    """Thin orchestrator wrapper.

    For now this only unifies the entrypoint into a single class and delegates to
    `handle_assistant_query()`.

    Later we can move routing/policy/handlers into methods without changing the
    FastAPI endpoint contract.
    """

    vault_root: Path
    commands_file: Path

    def run(
        self,
        *,
        query: str,
        vault_name: str,
        prefer: str = "most_hits",
        heading: str | None = None,
        section: str | None = None,
    ):
        return handle_assistant_query(
            query=query,
            vault_name=vault_name,
            vault_root=self.vault_root,
            commands_file=self.commands_file,
            obsidian_open_url_func=obsidian_open_url,
            prefer=prefer,
            heading=heading,
            section=section,
        )


ASSISTANT = AssistantOrchestrator(vault_root=VAULT_ROOT, commands_file=COMMANDS_FILE)


@app.get("/health")
def health(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "ok",
        "service": "obsidian-api",
        "version": "0.3.0",
        "time": datetime.now().astimezone().isoformat()
    }

@app.get("/obsidian-api/health")
def obsidian_api_health(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "ok",
        "service": "obsidian-api",
        "version": "0.3.0",
        "time": datetime.now().astimezone().isoformat()
    }


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
def note(
    path: str = Query(..., description="Vault-relative path like Foo/Bar.md"),
    section: str | None = Query(default=None, description="Heading title to extract, exact match"),
    with_frontmatter: bool = True,
):
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
def resolve_open_target(
    q: str = Query(..., min_length=1),
    prefer: str = Query(default="most_hits"),
):
    r = resolve_query(query=q, vault_root=VAULT_ROOT, commands_file=COMMANDS_FILE, prefer=prefer)
    return r.model_dump()


def obsidian_open_urls(vault_name: str, open_path: str, heading: str | None = None) -> dict[str, str]:
    """Build Obsidian URIs.

    Observed behavior differs by environment:
    - Some resolve `file=` without `.md`
    - Others require `.md`

    To make debugging and Shortcuts logic easier, return both.
    """
    # Normalize path separators just in case
    norm = open_path.replace("\\", "/")

    # Build both variants
    without_md = norm[:-3] if norm.lower().endswith(".md") else norm
    with_md = norm if norm.lower().endswith(".md") else norm + ".md"

    vault_enc = quote(vault_name, safe="")

    def _build(file_value: str) -> str:
        file_enc = quote(file_value, safe="/")
        url = f"obsidian://open?vault={vault_enc}&file={file_enc}"
        if heading:
            url += "%23" + quote(heading, safe="")
        return url

    return {
        "without_md": _build(without_md),
        "with_md": _build(with_md),
    }


def obsidian_open_url(vault_name: str, open_path: str, heading: str | None = None) -> str:
    """Backward-compatible single URL.

    Prefer the no-extension form (Obsidian wikilink-style), but callers that
    need the `.md` form can use `obsidian_open_urls()`.
    """
    return obsidian_open_urls(vault_name, open_path, heading=heading)["without_md"]


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

    urls = obsidian_open_urls(vault, r.open_path, heading=heading)
    return {
        "found": True,
        "source": r.source,
        "open_path": r.open_path,
        "obsidian_url": urls["without_md"],
        "obsidian_urls": urls,
        "candidates": r.candidates,
    }


@app.get("/assistant", dependencies=[Depends(require_api_key)])
def assistant(
    q: str = Query(..., min_length=1, description="User query / voice command"),
    vault: str = Query(..., min_length=1, description="Mac側ObsidianのVault名（表示名）"),
    prefer: str = Query(default="most_hits"),
    heading: str | None = Query(default=None),
    section: str | None = Query(default=None),
):
    return ASSISTANT.run(
        query=q,
        vault_name=vault,
        prefer=prefer,
        heading=heading,
        section=section,
    )
