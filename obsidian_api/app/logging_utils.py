import logging
import time
from typing import Optional


def setup_orchestrator_logger(name: str = "orchestrator", level: str = "INFO") -> logging.Logger:
    """Setup standardized logger for orchestrator operations."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:  # Avoid duplicate handlers
        handler = logging.StreamHandler()
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
                 error: Optional[str] = None) -> None:
    """Log key execution details in a structured format."""
    
    log_data = {
        "session_id": session_id,
        "query": query,
        "intent": intent,
        "confidence": confidence,
        "method": method,
        "success": success,
        "duration_ms": duration_ms,
        "action": action
    }
    
    if error:
        log_data["error"] = error
        logger.error(f"Execution failed: {log_data}")
    else:
        logger.info(f"Execution completed: {log_data}")


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