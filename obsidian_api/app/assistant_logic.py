from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Literal

from pydantic import BaseModel, Field

from .intent import detect_intent, Intent
from .resolver import resolve_query
from .vault import safe_join, parse_frontmatter, extract_section
from .table_extractor import extract_tables
from .search import grep_vault

try:
    # Optional: only used when LLM planner is enabled
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


Action = Literal["open", "search", "read", "summarize", "table", "help"]


class Plan(BaseModel):
    action: Action = Field(..., description="What to do next")
    keywords: Optional[str] = Field(None, description="Search keywords for vault grep")
    note_hint: Optional[str] = Field(None, description="Note name/path hint to resolve")
    section_hint: Optional[str] = Field(None, description="Section heading hint")
    user_message: str = Field(..., description="Short message to show to user")


def _llm_planner_enabled() -> bool:
    return (
        os.environ.get("ENABLE_LLM_PLANNER", "").strip() == "1"
        and os.environ.get("OPENAI_API_KEY", "").strip() != ""
        and OpenAI is not None
    )


def plan_with_llm(query: str) -> Optional[Plan]:
    """Return a Plan using OpenAI when enabled; otherwise None.

    This is intentionally conservative: if anything fails, return None and fall back
    to the existing rule-based intent detection.
    """
    if not _llm_planner_enabled():
        return None

    model = os.environ.get("OPENAI_PLANNER_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    instructions = (
        "You are a command planner for an Obsidian Vault API. "
        "Decide one action: open/search/read/summarize/table/help. "
        "If unclear, choose help and ask ONE short question in user_message. "
        "Prefer open when the user clearly names a note. "
        "For search, fill keywords. For read/summarize/table, fill note_hint and optionally section_hint. "
        "Return JSON that matches the provided schema."
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Prefer structured parsing if available; fall back to JSON extraction.
    try:
        resp = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": query},
            ],
            text_format=Plan,
        )
        return resp.output_parsed
    except Exception:
        try:
            resp = client.responses.create(
                model=model,
                input=query,
                instructions=instructions,
            )
            raw = getattr(resp, "output_text", "") or ""
            # Expect the model to return a single JSON object
            data = json.loads(raw)
            return Plan.model_validate(data)
        except Exception:
            return None


def _plan_to_intent(plan: Plan) -> Intent:
    if plan.action == "open":
        return Intent.OPEN
    if plan.action == "table":
        return Intent.TABLE
    if plan.action == "summarize":
        return Intent.SUMMARY
    if plan.action == "read":
        # "read" is best represented by returning text (no open URL)
        return Intent.UNKNOWN
    if plan.action == "search":
        return Intent.UNKNOWN
    return Intent.UNKNOWN

def handle_assistant_query(
    query: str,
    vault_name: str,
    vault_root: Path,
    commands_file: Path,
    obsidian_open_url_func,
    prefer: str = "most_hits",
    heading: Optional[str] = None,
    section: Optional[str] = None,
):
    # 1) Optional LLM-based planning (fallbacks to rule-based intent)
    plan = plan_with_llm(query)
    intent = _plan_to_intent(plan) if plan else detect_intent(query)

    # Use the planner's hint for resolution when provided
    resolve_input = (plan.note_hint if plan and plan.note_hint else query)

    # 2) Special-case: vault search can be answered without resolving a note
    if plan and plan.action == "search":
        kw = (plan.keywords or query).strip()
        hits = grep_vault(vault_root, kw, limit=30)
        return {
            "ok": True,
            "found": True,
            "intent": "search",
            "plan": plan.model_dump(),
            "q": kw,
            "hits": hits,
        }

    if plan and plan.action == "help":
        return {"ok": True, "found": False, "intent": "help", "plan": plan.model_dump()}

    rr = resolve_query(query=resolve_input, vault_root=vault_root, commands_file=commands_file, prefer=prefer)
    if not rr.found or not rr.open_path:
        return {"ok": False, "intent": intent, "reason": rr.reason, "found": False}

    note_path = rr.open_path
    resp = {
        "ok": True,
        "found": True,
        "intent": intent,
        "source": rr.source,
        "open_path": note_path,
        "candidates": rr.candidates,
    }
    if plan:
        resp["plan"] = plan.model_dump()

    if intent == Intent.OPEN or intent == Intent.UNKNOWN:
        # If the planner suggests a section, use it as heading unless explicitly provided
        heading2 = heading
        if heading2 is None and plan and plan.section_hint:
            heading2 = plan.section_hint
        resp["obsidian_url"] = obsidian_open_url_func(vault_name, note_path, heading=heading2)
        return resp

    p = safe_join(vault_root, note_path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    fm, body = parse_frontmatter(text)
    resp["frontmatter"] = fm

    section2 = section
    if section2 is None and plan and plan.section_hint:
        section2 = plan.section_hint

    if section2:
        sec = extract_section(body, section2)
        resp["text"] = sec if sec is not None else ""
        resp["section"] = section2
        return resp

    if intent == Intent.TABLE:
        resp["tables"] = extract_tables(text)
        resp["count"] = len(resp["tables"])
        return resp

    if intent == Intent.SUMMARY:
        snippet = body.strip().splitlines()
        resp["summary"] = "\n".join(snippet[:20]).strip()
        return resp

    resp["text"] = body
    return resp
