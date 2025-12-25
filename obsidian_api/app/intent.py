from enum import Enum

class Intent(str, Enum):
    OPEN = "open"
    TABLE = "table"
    SUMMARY = "summary"
    NOTE = "note"
    UNKNOWN = "unknown"

def detect_intent(text: str) -> Intent:
    t = (text or "").lower()
    if any(k in t for k in ["表", "table", "一覧"]):
        return Intent.TABLE
    if any(k in t for k in ["要約", "summary", "まとめ"]):
        return Intent.SUMMARY
    if any(k in t for k in ["開", "open", "表示"]):
        return Intent.OPEN
    if any(k in t for k in ["ノート", "全文", "本文"]):
        return Intent.NOTE
    return Intent.UNKNOWN
