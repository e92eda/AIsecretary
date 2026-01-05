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


def _add_shortcut_keys(data: dict) -> dict:
    """Add helper keys for Apple Shortcuts decision making"""
    # Create a copy to avoid modifying original data
    enhanced_data = data.copy()
    
    action = data.get('action', '')
    obsidian_url = data.get('obsidian_url', '')
    
    # Add shortcut action type
    if action == 'open' and obsidian_url:
        enhanced_data['shortcut_action'] = 'open_obsidian'
        enhanced_data['should_open_obsidian'] = True
    elif action in ['search', 'read', 'comment', 'summarize']:
        enhanced_data['shortcut_action'] = 'display_content'
        enhanced_data['should_open_obsidian'] = False
    elif action == 'list_files':
        enhanced_data['shortcut_action'] = 'display_list'
        enhanced_data['should_open_obsidian'] = False
    else:
        enhanced_data['shortcut_action'] = 'display_content'
        enhanced_data['should_open_obsidian'] = False
    
    # Add easy access to key info
    if obsidian_url:
        enhanced_data['obsidian_ready'] = True
    else:
        enhanced_data['obsidian_ready'] = False
    
    return enhanced_data


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
        # Add shortcut helper keys for JSON responses
        if content_type == "assistant":
            data = _add_shortcut_keys(data)
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
    
    # Add shortcut keys for HTML format too
    if content_type == "assistant":
        enhanced_data = _add_shortcut_keys(data)
        shortcut_metadata = {
            "should_open_obsidian": enhanced_data.get("should_open_obsidian", False),
            "shortcut_action": enhanced_data.get("shortcut_action", "display_content"),
            "obsidian_url": enhanced_data.get("obsidian_url", ""),
            "obsidian_ready": enhanced_data.get("obsidian_ready", False)
        }
    else:
        shortcut_metadata = {"shortcut_action": "display_content", "should_open_obsidian": False}
    
    # Create HTML renderer with dynamic settings
    renderer = HtmlRenderer(
        theme=css_theme,
        mobile_optimized=mobile
    )
    
    html_content = renderer.render(markdown, title, shortcut_metadata)
    
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

    Use the .md extension form for better compatibility.
    """
    return obsidian_open_urls(vault_name, open_path, heading=heading)["with_md"]


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


@app.get("/test")
def run_simple_tests():
    """Run simple in-app tests to verify functionality"""
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": [],
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0
        }
    }
    
    def add_test(name: str, passed: bool, details: str = ""):
        results["tests"].append({
            "name": name,
            "status": "PASS" if passed else "FAIL", 
            "details": details
        })
        results["summary"]["total"] += 1
        if passed:
            results["summary"]["passed"] += 1
        else:
            results["summary"]["failed"] += 1
    
    # Test 1: Vault accessibility
    try:
        vault_exists = VAULT_ROOT.exists()
        add_test("Vault Root Exists", vault_exists, f"Path: {VAULT_ROOT}")
        
        if vault_exists:
            md_files = list(VAULT_ROOT.glob("*.md"))
            add_test("Has MD Files", len(md_files) > 0, f"Found {len(md_files)} .md files")
    except Exception as e:
        add_test("Vault Root Exists", False, f"Error: {str(e)}")
    
    # Test 2: Intent classifier
    try:
        classifier = create_classifier()
        test_query = "テスト"
        intent_result, metrics = classifier.classify(test_query)
        
        add_test("Intent Classification", 
                intent_result.intent in [Intent.OPEN, Intent.SEARCH, Intent.READ, Intent.SUMMARIZE, Intent.COMMENT, Intent.UPDATE, Intent.TABLE, Intent.UNKNOWN],
                f"Intent: {intent_result.intent.value}, Confidence: {intent_result.confidence:.2f}, Model: {metrics.model_used}")
    except Exception as e:
        add_test("Intent Classification", False, f"Error: {str(e)}")
    
    # Test 3: HTML renderer
    try:
        renderer = HtmlRenderer()
        test_md = "# Test\n\nThis is **bold** text."
        html = renderer.render(test_md, "Test")
        
        has_html_structure = all(tag in html for tag in ["<html>", "<body>", "<h1>", "<strong>"])
        add_test("HTML Rendering", has_html_structure, f"Generated {len(html)} chars")
    except Exception as e:
        add_test("HTML Rendering", False, f"Error: {str(e)}")
    
    # Test 4: Configuration
    try:
        config_ok = all([
            hasattr(settings, 'vault_root'),
            hasattr(settings, 'aisecretary_api_key'),
            hasattr(settings, 'css_theme')
        ])
        add_test("Configuration", config_ok, f"Theme: {getattr(settings, 'css_theme', 'N/A')}")
    except Exception as e:
        add_test("Configuration", False, f"Error: {str(e)}")
    
    # Test 5: Search functionality
    try:
        if VAULT_ROOT.exists():
            search_results = grep_vault("test", VAULT_ROOT)
            add_test("Search Engine", True, f"Search completed, found {len(search_results)} results")
        else:
            add_test("Search Engine", False, "Vault not accessible")
    except Exception as e:
        add_test("Search Engine", False, f"Error: {str(e)}")
    
    return results


@app.get("/test/intent")
def test_intent_classification(q: str = Query("部品を開いて", description="Test query")):
    """Test intent classification with custom query"""
    
    try:
        classifier = create_classifier()
        intent_result, metrics = classifier.classify(q)
        
        return {
            "query": q,
            "result": {
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "extracted_note": intent_result.extracted_note
            },
            "metrics": {
                "model_used": metrics.model_used,
                "latency_ms": metrics.latency_ms,
                "tokens_used": getattr(metrics, 'tokens_used', None)
            }
        }
    except Exception as e:
        return {
            "query": q,
            "error": str(e)
        }


@app.get("/test/search")
def test_search_functionality(
    q: str = Query("test", description="Search query"),
    vault: str = Query("", description="Vault name (optional)")
):
    """Test search functionality"""
    
    try:
        vault_path = safe_join(VAULT_ROOT, vault) if vault else VAULT_ROOT
        
        search_results = grep_vault(q, vault_path)
        
        return {
            "query": q,
            "vault": vault or "root",
            "results": {
                "count": len(search_results),
                "files": [
                    {
                        "file": result["file"],
                        "matches": len(result["matches"])
                    } for result in search_results[:5]  # First 5 results
                ]
            }
        }
    except Exception as e:
        return {
            "query": q,
            "vault": vault,
            "error": str(e)
        }


@app.get("/test/html")
def test_html_rendering(
    theme: str = Query("obsidian", description="CSS theme"),
    mobile: bool = Query(True, description="Mobile optimization")
):
    """Test HTML rendering with different themes"""
    
    try:
        renderer = HtmlRenderer(theme=theme, mobile_optimized=mobile)
        
        test_markdown = """# テストページ

これは**太字**テキストと*斜体*テキストです。

## リスト
- アイテム 1
- アイテム 2
- アイテム 3

## コード
```python
print("Hello, World!")
```

## テーブル
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| 1   | 2   | 3   |

## リンク
[AIsecretary Documentation](../README.md)
"""
        
        html = renderer.render(test_markdown, "テスト")
        
        # Return just metrics for JSON response
        return {
            "theme": theme,
            "mobile_optimized": mobile,
            "result": {
                "html_size": len(html),
                "has_css": "style>" in html,
                "has_content": "テストページ" in html,
                "mobile_meta": 'viewport' in html if mobile else "N/A"
            },
            "sample_url": f"/test/html/view?theme={theme}&mobile={mobile}"
        }
    except Exception as e:
        return {
            "theme": theme,
            "mobile_optimized": mobile,
            "error": str(e)
        }


@app.get("/test/html/view")
def view_test_html(
    theme: str = Query("obsidian", description="CSS theme"),
    mobile: bool = Query(True, description="Mobile optimization")
):
    """View test HTML rendering (returns actual HTML)"""
    
    try:
        renderer = HtmlRenderer(theme=theme, mobile_optimized=mobile)
        
        test_markdown = """# テストページ - {theme}

これは**太字**テキストと*斜体*テキストです。

## 機能テスト

### リスト
- ✅ 基本マークダウン
- ✅ CSS テーマ: **{theme}**
- ✅ モバイル最適化: **{mobile}**

### コード
```python
# AIsecretary テスト
print("Theme: {theme}")
print("Mobile: {mobile}")
```

### テーブル
| 項目 | 値 | 状態 |
|------|-----|------|
| テーマ | {theme} | ✅ |
| モバイル | {mobile} | ✅ |
| 日本語 | あいうえお | ✅ |

### 特殊文字
**日本語**: こんにちは、世界！  
**記号**: →←↑↓ ★☆ ◆◇ ●○  
**絵文字**: 🚀 🎯 🔍 📱 💻

---

**テスト完了** - {theme} テーマ、モバイル最適化: {mobile}
""".format(theme=theme, mobile="有効" if mobile else "無効")
        
        html = renderer.render(test_markdown, f"テスト - {theme}")
        
        return Response(content=html, media_type="text/html; charset=utf-8")
        
    except Exception as e:
        error_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Test Error</title></head>
<body><h1>テストエラー</h1><p>Error: {str(e)}</p></body></html>"""
        return Response(content=error_html, media_type="text/html; charset=utf-8")
