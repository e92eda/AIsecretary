import logging
import time
from typing import Optional


def setup_orchestrator_logger(name: str = "orchestrator", level: str = "DEBUG") -> logging.Logger:
    """Setup standardized logger for orchestrator operations with UTF-8 support."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:  # Avoid duplicate handlers
        handler = logging.StreamHandler()
        # Ensure UTF-8 encoding for Japanese text
        if hasattr(handler.stream, 'reconfigure'):
            handler.stream.reconfigure(encoding='utf-8')
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(getattr(logging, level.upper()))
    return logger


def log_execution(logger: logging.Logger, 
                 session_id: str,
                 query: str, 
                 intent: str, 
                 confidence: float,
                 method: str,
                 success: bool, 
                 duration_ms: float,
                 action: str,
                 result_summary: Optional[str] = None,
                 routing_info: Optional[str] = None,
                 fallback_used: bool = False,
                 response_data: Optional[dict] = None,
                 execution_steps: Optional[list] = None,
                 error: Optional[str] = None) -> None:
    """Log comprehensive execution details in a structured format."""
    
    log_data = {
        "session_id": session_id,
        "query": query,
        "intent_detected": intent,
        "confidence": round(confidence, 3),
        "classification_method": method,
        "final_action": action,
        "success": success,
        "duration_ms": round(duration_ms, 1)
    }
    
    # Add routing information
    if routing_info:
        log_data["routing"] = routing_info
    
    # Mark if fallback was used
    if fallback_used:
        log_data["fallback_triggered"] = True
    
    # Add result summary
    if result_summary:
        log_data["result"] = result_summary
    
    # Add execution steps for process visibility
    if execution_steps:
        step_summary = []
        for step in execution_steps:
            step_info = f"{step}ms" if isinstance(step, (int, float)) else str(step)
            step_summary.append(step_info)
        log_data["process_steps"] = step_summary
    
    # Add response details (sanitized)
    if response_data:
        response_summary = _sanitize_response_data(response_data)
        if response_summary:
            log_data["response"] = response_summary
    
    # Add error information
    if error:
        log_data["error"] = error
    
    # Format log message with Japanese support
    status_icon = "✅" if success else "❌"
    action_desc = action.replace("_", " ").title()
    
    if error:
        logger.error(f"{status_icon} {action_desc}: {log_data}")
    else:
        logger.info(f"{status_icon} {action_desc}: {log_data}")


def _sanitize_response_data(response_data: dict) -> dict:
    """Extract key information from response data for logging."""
    sanitized = {}
    
    # Include useful fields with more comprehensive coverage
    useful_fields = [
        "intent", "confidence", "user_message", "found", "source", 
        "action", "success", "open_path", "reason"
    ]
    
    for field in useful_fields:
        if field in response_data:
            value = response_data[field]
            # Truncate very long messages but keep reasonable length
            if isinstance(value, str) and len(value) > 200:
                sanitized[field] = value[:197] + "..."
            else:
                sanitized[field] = value
    
    # Add count and content information
    if "hits" in response_data:
        hits = response_data["hits"]
        sanitized["hits_count"] = len(hits)
        # Show first few file names
        if hits:
            file_names = [hit.get("file", "unknown") for hit in hits[:3]]
            sanitized["sample_files"] = file_names
            if len(hits) > 3:
                sanitized["more_files"] = len(hits) - 3
    
    if "tables" in response_data:
        tables = response_data["tables"]
        sanitized["tables_count"] = len(tables)
        # Show table info briefly
        if tables:
            sanitized["table_info"] = f"{len(tables)} tables found"
    
    # Add text content info
    if "text" in response_data:
        text = response_data["text"]
        sanitized["text_length"] = len(text)
        # Show first line or part for context
        if text:
            first_line = text.split('\n')[0][:100]
            sanitized["text_preview"] = first_line + ("..." if len(first_line) == 100 else "")
    
    # Add URL info with actual path for debugging
    if "obsidian_url" in response_data:
        url = response_data["obsidian_url"]
        sanitized["obsidian_url"] = url
        # Extract file name from URL for quick reference
        if "file=" in url:
            try:
                file_part = url.split("file=")[1].split("&")[0].split("#")[0]
                from urllib.parse import unquote
                sanitized["target_file"] = unquote(file_part)
            except:
                sanitized["target_file"] = "unknown"
    
    # Add clarification info
    if "clarification" in response_data:
        clarification = response_data["clarification"]
        sanitized["clarification_options"] = len(clarification.get("options", []))
    
    # Add candidates info
    if "candidates" in response_data:
        candidates = response_data["candidates"]
        sanitized["candidates_count"] = len(candidates) if isinstance(candidates, list) else 0
        if isinstance(candidates, list) and candidates:
            # Show first few candidates
            sanitized["top_candidates"] = candidates[:3]
    
    return sanitized


def create_session_id() -> str:
    """Create unique session ID for tracking."""
    return f"session_{int(time.time() * 1000)}"


def measure_time(func):
    """Simple decorator to measure execution time."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration_ms = (time.time() - start_time) * 1000
        return result, duration_ms
    return wrapper