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
from .intent import IntentClassifier, Intent, IntentResult
from .routing import RoutingPolicy, Action, ClarificationGenerator
from .classifier_factory import create_classifier, ClassifierType
from .logging_utils import setup_orchestrator_logger, log_execution, create_session_id


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
    """Orchestrator that coordinates intent classification, routing, and execution.

    Phase 2 implementation with:
    - LLM-based intent classification (with rule-based fallback)
    - A/B testing support
    - Comprehensive logging and metrics
    - Routing policy for fallback and clarification
    - Delegation to existing execution logic
    """

    vault_root: Path
    commands_file: Path
    routing_policy: RoutingPolicy = RoutingPolicy()
    clarification_generator: ClarificationGenerator = ClarificationGenerator()
    
    def __post_init__(self):
        # Create unified classifier and logger based on configuration
        object.__setattr__(self, 'classifier', create_classifier())
        object.__setattr__(self, 'logger', setup_orchestrator_logger())

    def run(
        self,
        *,
        query: str,
        vault_name: str,
        prefer: str = "most_hits",
        heading: str | None = None,
        section: str | None = None,
    ):
        """Main orchestration entry point with simple logging."""
        
        session_id = create_session_id()
        import time
        start_time = time.time()
        
        try:
            # Step 1: Classify intent
            intent_result, classification_metrics = self.classifier.classify(query)
            
            # Step 2: Determine routing decision
            routing_decision = self.routing_policy.decide(intent_result)
            
            # Step 3: Handle based on routing decision
            if routing_decision.action == Action.CLARIFY:
                clarification = self.clarification_generator.generate_clarification(intent_result)
                
                duration_ms = (time.time() - start_time) * 1000
                log_execution(
                    self.logger, session_id, query, intent_result.intent.value,
                    intent_result.confidence, classification_metrics.model_used,
                    False, duration_ms, "clarify"
                )
                
                return {
                    "action": "clarify",
                    "success": False,
                    "intent": intent_result.intent.value,
                    "confidence": intent_result.confidence,
                    "clarification": clarification,
                    "user_message": clarification["question"],
                    "session_id": session_id,
                    "duration_ms": duration_ms
                }
            
            # Step 4: Execute the intent
            result = self._execute_intent(
                intent_result=intent_result,
                vault_name=vault_name,
                prefer=prefer,
                heading=heading,
                section=section
            )
            
            # Check execution success
            if result.get("ok", False) or result.get("found", False):
                response = self._format_success_response(result, intent_result, routing_decision)
                
                duration_ms = (time.time() - start_time) * 1000
                log_execution(
                    self.logger, session_id, query, intent_result.intent.value,
                    intent_result.confidence, classification_metrics.model_used,
                    True, duration_ms, response.get("action", "unknown")
                )
                
                response["session_id"] = session_id
                response["duration_ms"] = duration_ms
                return response
            
            # Try fallback if available
            if routing_decision.fallback_intent:
                fallback_result = self._try_fallback(
                    original_intent=intent_result.intent,
                    fallback_intent=routing_decision.fallback_intent,
                    query=query,
                    vault_name=vault_name,
                    prefer=prefer,
                    heading=heading,
                    section=section
                )
                
                if fallback_result and (fallback_result.get("ok", False) or fallback_result.get("found", False)):
                    response = self._format_fallback_response(fallback_result, intent_result, routing_decision)
                    
                    duration_ms = (time.time() - start_time) * 1000
                    log_execution(
                        self.logger, session_id, query, intent_result.intent.value,
                        intent_result.confidence, classification_metrics.model_used,
                        True, duration_ms, "fallback_" + response.get("action", "unknown")
                    )
                    
                    response["session_id"] = session_id
                    response["duration_ms"] = duration_ms
                    return response
            
            # Execution failed
            response = self._format_failure_response(result, intent_result, routing_decision)
            
            duration_ms = (time.time() - start_time) * 1000
            log_execution(
                self.logger, session_id, query, intent_result.intent.value,
                intent_result.confidence, classification_metrics.model_used,
                False, duration_ms, "failed", result.get("reason", "Unknown error")
            )
            
            response["session_id"] = session_id
            response["duration_ms"] = duration_ms
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            log_execution(
                self.logger, session_id, query, "unknown", 0.0, "unknown",
                False, duration_ms, "error", str(e)
            )
            
            return {
                "action": "error",
                "success": False,
                "intent": "unknown",
                "error": str(e),
                "user_message": "処理中にエラーが発生しました",
                "session_id": session_id,
                "duration_ms": duration_ms
            }

    def _execute_intent(
        self,
        intent_result,
        vault_name: str,
        prefer: str = "most_hits",
        heading: str | None = None,
        section: str | None = None,
    ):
        """Execute intent using existing assistant logic."""
        return handle_assistant_query(
            query=intent_result.entities["query"],
            vault_name=vault_name,
            vault_root=self.vault_root,
            commands_file=self.commands_file,
            obsidian_open_url_func=obsidian_open_url,
            prefer=prefer,
            heading=heading,
            section=section,
        )
    
    def _try_fallback(
        self,
        original_intent: Intent,
        fallback_intent: Intent,
        query: str,
        vault_name: str,
        prefer: str = "most_hits",
        heading: str | None = None,
        section: str | None = None,
    ):
        """Try executing fallback intent."""
        try:
            # Create a fallback intent result
            fallback_entities = {"query": query, "note": None, "section": None, "vault": None}
            fallback_result_obj = IntentResult(
                intent=fallback_intent,
                confidence=0.8,  # High confidence for fallback
                entities=fallback_entities
            )
            
            return self._execute_intent(
                intent_result=fallback_result_obj,
                vault_name=vault_name,
                prefer=prefer,
                heading=heading,
                section=section
            )
        except Exception:
            return None
    
    def _format_success_response(self, result, intent_result, routing_decision):
        """Format successful execution response."""
        action_name = self._intent_to_action_name(intent_result.intent)
        
        response = {
            "action": action_name,
            "success": True,
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "routing_reason": routing_decision.reason,
            **result
        }
        
        # Add user-friendly message
        if "obsidian_url" in result:
            response["user_message"] = "ノートを開きました"
        elif "hits" in result:
            response["user_message"] = f"{len(result['hits'])}件の検索結果を見つけました"
        elif "text" in result:
            response["user_message"] = "ノート内容を取得しました"
        elif "tables" in result:
            response["user_message"] = f"{result.get('count', 0)}個のテーブルを見つけました"
        else:
            response["user_message"] = "処理が完了しました"
            
        return response
    
    def _format_fallback_response(self, result, intent_result, routing_decision):
        """Format fallback execution response."""
        action_name = self._intent_to_action_name(routing_decision.fallback_intent)
        
        response = {
            "action": action_name,
            "success": True,
            "intent": intent_result.intent.value,
            "fallback_intent": routing_decision.fallback_intent.value,
            "confidence": intent_result.confidence,
            "routing_reason": "Fallback executed after original intent failed",
            **result
        }
        
        response["user_message"] = f"元の操作に失敗したため、{action_name}を実行しました"
        return response
    
    def _format_failure_response(self, result, intent_result, routing_decision):
        """Format failure response."""
        return {
            "action": "failed",
            "success": False,
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "routing_reason": routing_decision.reason,
            "reason": result.get("reason", "Unknown error"),
            "user_message": "申し訳ありませんが、処理できませんでした"
        }
    
    def _intent_to_action_name(self, intent: Intent) -> str:
        """Convert intent to action name for response."""
        mapping = {
            Intent.OPEN: "open",
            Intent.SEARCH: "search", 
            Intent.READ: "read",
            Intent.SUMMARIZE: "summarize",
            Intent.TABLE: "table",
            Intent.COMMENT: "comment",
            Intent.UPDATE: "update"
        }
        return mapping.get(intent, "unknown")


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
