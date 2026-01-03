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
from .presentation.html_renderer import HtmlRenderer
from .presentation.presenters import create_presenter


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
                    False, duration_ms, "clarify", 
                    result_summary=f"asking: {clarification['question'][:50]}...",
                    routing_info=f"action={routing_decision.action.value}, reason={routing_decision.reason}",
                    response_data={
                        "action": "clarify",
                        "user_message": clarification["question"],
                        "options_count": len(clarification.get("options", []))
                    }
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
                result_summary = self._create_result_summary(result, response)
                log_execution(
                    self.logger, session_id, query, intent_result.intent.value,
                    intent_result.confidence, classification_metrics.model_used,
                    True, duration_ms, response.get("action", "unknown"),
                    result_summary=result_summary,
                    routing_info=f"action={routing_decision.action.value}, confidence_gate=passed",
                    response_data=response
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
                    result_summary = self._create_result_summary(fallback_result, response)
                    log_execution(
                        self.logger, session_id, query, intent_result.intent.value,
                        intent_result.confidence, classification_metrics.model_used,
                        True, duration_ms, "fallback_" + response.get("action", "unknown"),
                        result_summary=f"fallback: {result_summary}",
                        routing_info=f"original_failed -> fallback_to_{routing_decision.fallback_intent.value}",
                        fallback_used=True,
                        response_data=response
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
                False, duration_ms, "failed", 
                routing_info=f"execution_failed, no_fallback_available",
                error=result.get("reason", "Unknown error")
            )
            
            response["session_id"] = session_id
            response["duration_ms"] = duration_ms
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            log_execution(
                self.logger, session_id, query, "unknown", 0.0, "unknown",
                False, duration_ms, "error", error=str(e)
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
    
    def _create_result_summary(self, result: dict, response: dict) -> str:
        """Create a short summary of execution results."""
        if "obsidian_url" in response:
            note_path = result.get("open_path", "unknown")
            return f"opened: {note_path}"
        elif "hits" in result:
            count = len(result["hits"])
            return f"found: {count} matches"
        elif "text" in result:
            text_len = len(result.get("text", ""))
            return f"read: {text_len} chars"
        elif "tables" in result:
            count = result.get("count", 0)
            return f"extracted: {count} tables"
        else:
            return "completed"


ASSISTANT = AssistantOrchestrator(vault_root=VAULT_ROOT, commands_file=COMMANDS_FILE)


def _format_response(
    data: dict, 
    format: str = "json",
    content_type: str = "assistant",
    title: str = "AIsecretary",
    css_theme: str | None = None,
    mobile: bool | None = None
):
    """Format response based on requested format"""
    if format.lower() != "html":
        return data
    
    # Create presenter and convert to markdown
    presenter = create_presenter(content_type)
    
    if content_type == "files":
        markdown = presenter.to_markdown(data.get("files", []), "")
    elif content_type == "search":
        markdown = presenter.to_markdown(data.get("hits", []), data.get("q", ""))
    elif content_type == "note":
        markdown = presenter.to_markdown(data.get("text", ""), data.get("path", ""))
    elif content_type == "resolve":
        # Resolve returns candidates in a different format
        candidates = []
        if data.get("found"):
            candidates = [{"name": data.get("open_path", ""), "score": 1.0, "path": data.get("open_path", "")}]
        elif data.get("candidates"):
            candidates = data.get("candidates", [])
        markdown = presenter.to_markdown(candidates, data.get("query", ""))
    elif content_type == "assistant":
        markdown = presenter.to_markdown(data)
    else:
        # Fallback: convert dict to simple markdown
        import json
        markdown = f"# {title}\n\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
    
    # Create HTML renderer with dynamic settings
    renderer = HtmlRenderer(
        theme=css_theme,
        mobile_optimized=mobile
    )
    
    html_content = renderer.render(markdown, title)
    
    return Response(content=html_content, media_type="text/html; charset=utf-8")


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
def files(
    format: str = Query(default="json", description="Response format: json|html"),
    css_theme: str | None = Query(default=None, description="CSS theme for HTML: obsidian|light|dark|minimal"),
    mobile: bool | None = Query(default=None, description="Mobile optimization for HTML")
):
    if not VAULT_ROOT.exists():
        raise HTTPException(500, detail="VAULT_ROOT not found")
    
    result = {"files": list_md_files(VAULT_ROOT)}
    
    return _format_response(
        data=result,
        format=format,
        content_type="files",
        title="ファイル一覧",
        css_theme=css_theme,
        mobile=mobile
    )


@app.get("/search", dependencies=[Depends(require_api_key)])
def search(
    q: str = Query(..., min_length=1), 
    limit: int = 30,
    format: str = Query(default="json", description="Response format: json|html"),
    css_theme: str | None = Query(default=None, description="CSS theme for HTML: obsidian|light|dark|minimal"),
    mobile: bool | None = Query(default=None, description="Mobile optimization for HTML")
):
    if not VAULT_ROOT.exists():
        raise HTTPException(500, detail="VAULT_ROOT not found")
    
    result = {"q": q, "hits": grep_vault(VAULT_ROOT, q, limit=limit)}
    
    return _format_response(
        data=result,
        format=format,
        content_type="search",
        title=f"検索結果: {q}",
        css_theme=css_theme,
        mobile=mobile
    )


@app.get("/note", dependencies=[Depends(require_api_key)])
def note(
    path: str = Query(..., description="Vault-relative path like Foo/Bar.md"),
    section: str | None = Query(default=None, description="Heading title to extract, exact match"),
    with_frontmatter: bool = True,
    format: str = Query(default="json", description="Response format: json|html"),
    css_theme: str | None = Query(default=None, description="CSS theme for HTML: obsidian|light|dark|minimal"),
    mobile: bool | None = Query(default=None, description="Mobile optimization for HTML")
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
    
    # Create title for HTML display
    filename = path.split('/')[-1] if '/' in path else path
    filename = filename.replace('.md', '')
    title = f"ノート: {filename}"
    if section:
        title += f" - {section}"
    
    return _format_response(
        data=resp,
        format=format,
        content_type="note",
        title=title,
        css_theme=css_theme,
        mobile=mobile
    )


@app.get("/resolve", dependencies=[Depends(require_api_key)])
def resolve_open_target(
    q: str = Query(..., min_length=1),
    prefer: str = Query(default="most_hits"),
    format: str = Query(default="json", description="Response format: json|html"),
    css_theme: str | None = Query(default=None, description="CSS theme for HTML: obsidian|light|dark|minimal"),
    mobile: bool | None = Query(default=None, description="Mobile optimization for HTML")
):
    r = resolve_query(query=q, vault_root=VAULT_ROOT, commands_file=COMMANDS_FILE, prefer=prefer)
    result = r.model_dump()
    
    return _format_response(
        data=result,
        format=format,
        content_type="resolve",
        title=f"解決候補: {q}",
        css_theme=css_theme,
        mobile=mobile
    )


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
    # Use the new orchestrator system with enhanced logging
    result = ASSISTANT.run(
        query=q,
        vault_name=vault,
        prefer=prefer,
        heading=heading,
        section=None,
    )
    
    # Transform orchestrator response to match /open API format for backward compatibility
    if result.get("success", False) and result.get("obsidian_url"):
        urls = obsidian_open_urls(vault, result.get("open_path", ""), heading=heading)
        return {
            "found": True,
            "source": result.get("source", "unknown"),
            "open_path": result.get("open_path", ""),
            "obsidian_url": urls["without_md"],
            "obsidian_urls": urls,
            "candidates": result.get("candidates", []),
            # Include orchestrator metadata for debugging
            "session_id": result.get("session_id"),
            "duration_ms": result.get("duration_ms"),
            "intent": result.get("intent"),
            "confidence": result.get("confidence")
        }
    else:
        return {
            "found": False,
            "obsidian_url": None,
            "reason": result.get("reason", result.get("user_message", "Unknown error")),
            # Include orchestrator metadata for debugging
            "session_id": result.get("session_id"),
            "duration_ms": result.get("duration_ms"),
            "intent": result.get("intent"),
            "confidence": result.get("confidence")
        }


@app.get("/assistant", dependencies=[Depends(require_api_key)])
def assistant(
    q: str = Query(..., min_length=1, description="User query / voice command"),
    vault: str = Query(..., min_length=1, description="Mac側ObsidianのVault名（表示名）"),
    prefer: str = Query(default="most_hits"),
    heading: str | None = Query(default=None),
    section: str | None = Query(default=None),
    format: str = Query(default="json", description="Response format: json|html"),
    css_theme: str | None = Query(default=None, description="CSS theme for HTML: obsidian|light|dark|minimal"),
    mobile: bool | None = Query(default=None, description="Mobile optimization for HTML")
):
    result = ASSISTANT.run(
        query=q,
        vault_name=vault,
        prefer=prefer,
        heading=heading,
        section=section,
    )
    
    return _format_response(
        data=result,
        format=format,
        content_type="assistant",
        title=f"AIsecretary: {q}",
        css_theme=css_theme,
        mobile=mobile
    )


# Core HTML endpoints
@app.post("/render_html", dependencies=[Depends(require_api_key)])
def render_html(
    content: dict,
    css_theme: str | None = Query(default=None, description="CSS theme: obsidian|light|dark|minimal"),
    mobile: bool | None = Query(default=None, description="Mobile optimization"),
    title: str = Query(default="AIsecretary", description="HTML document title")
):
    """Render arbitrary Markdown content to HTML"""
    markdown_text = content.get("markdown", "")
    
    if not markdown_text:
        raise HTTPException(400, detail="Missing 'markdown' field in request body")
    
    renderer = HtmlRenderer(
        theme=css_theme,
        mobile_optimized=mobile
    )
    
    html_content = renderer.render(markdown_text, title)
    return Response(content=html_content, media_type="text/html; charset=utf-8")


@app.get("/view_html", dependencies=[Depends(require_api_key)])
def view_html(
    path: str = Query(..., description="Vault-relative path to markdown file"),
    css_theme: str | None = Query(default=None, description="CSS theme: obsidian|light|dark|minimal"),
    mobile: bool | None = Query(default=None, description="Mobile optimization")
):
    """View a specific markdown file as HTML"""
    if not VAULT_ROOT.exists():
        raise HTTPException(500, detail="VAULT_ROOT not found")
    
    try:
        p = safe_join(VAULT_ROOT, path)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    
    if not p.exists():
        raise HTTPException(404, detail="Note not found")
    
    if not path.lower().endswith('.md'):
        raise HTTPException(400, detail="Only .md files are supported")
    
    # Read markdown content
    try:
        markdown_content = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to read file: {str(e)}")
    
    # Create title from filename
    filename = path.split('/')[-1] if '/' in path else path
    filename = filename.replace('.md', '')
    title = f"ノート: {filename}"
    
    # Render HTML
    renderer = HtmlRenderer(
        theme=css_theme,
        mobile_optimized=mobile
    )
    
    html_content = renderer.render(markdown_content, title)
    return Response(content=html_content, media_type="text/html; charset=utf-8")


@app.post("/save_md", dependencies=[Depends(require_api_key)])
def save_markdown(
    content: dict
):
    """Save markdown content to vault (restricted to configured write directory)"""
    path = content.get("path", "")
    markdown_content = content.get("content", "")
    overwrite = content.get("overwrite", True)
    
    if not path or not markdown_content:
        raise HTTPException(400, detail="Missing 'path' or 'content' field")
    
    if not path.lower().endswith('.md'):
        raise HTTPException(400, detail="Only .md files are supported")
    
    if not VAULT_ROOT.exists():
        raise HTTPException(500, detail="VAULT_ROOT not found")
    
    # Ensure path is restricted to vault_write_root for safety
    write_root_name = settings.vault_write_root
    if write_root_name:
        if not path.startswith(write_root_name + '/') and path != write_root_name:
            if '/' in path:
                # Path has subdirectory but doesn't start with write_root
                path = f"{write_root_name}/{path}"
            else:
                # Just a filename, put it in write_root
                path = f"{write_root_name}/{path}"
    
    try:
        full_path = safe_join(VAULT_ROOT, path)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    
    # Create parent directory if it doesn't exist
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if file exists and overwrite setting
    file_existed = full_path.exists()
    if file_existed and not overwrite:
        raise HTTPException(409, detail="File already exists and overwrite=false")
    
    try:
        # Write the markdown content
        full_path.write_text(markdown_content, encoding="utf-8")
        
        # Get file stats for response
        file_size = full_path.stat().st_size
        relative_path = str(full_path.relative_to(VAULT_ROOT)).replace("\\", "/")
        
        return {
            "success": True,
            "path": relative_path,
            "size_bytes": file_size,
            "overwritten": file_existed,
            "write_root_restricted": bool(write_root_name),
            "write_root": write_root_name
        }
        
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to save file: {str(e)}")
