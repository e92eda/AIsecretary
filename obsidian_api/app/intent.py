from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Intent(str, Enum):
    OPEN = "open"
    SEARCH = "search"
    READ = "read"
    SUMMARIZE = "summarize"
    COMMENT = "comment"
    UPDATE = "update"
    TABLE = "table"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentResult:
    intent: Intent
    confidence: float
    entities: dict[str, Optional[str]]


@dataclass(frozen=True)
class IntentClassifier:
    """Rule-based intent classifier for Phase 1.
    
    Later can be replaced with LLM-based classifier while keeping same interface.
    """
    
    def classify(self, text: str) -> IntentResult:
        """Classify user input and return intent with confidence."""
        t = (text or "").lower().strip()
        
        if not t:

            return IntentResult(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                entities={"query": None, "note": None, "section": None, "vault": None}
            )
        
        # Rule-based classification with confidence scores
        intent, confidence = self._detect_intent_with_confidence(t)
        entities = self._extract_entities(t, intent)
        
        return IntentResult(
            intent=intent,
            confidence=confidence,
            entities=entities
        )
    
    def _detect_intent_with_confidence(self, text: str) -> tuple[Intent, float]:
        """Detect intent with confidence score (0.0 - 1.0)."""
        
        # Very high confidence patterns (composite/specific patterns)
        # File listing requests
        if any(k in text for k in ["ファイル", "file"]) and any(k in text for k in ["リスト", "一覧", "list"]):
            return Intent.TABLE, 0.95
            
        # List/table display requests  
        if any(k in text for k in ["リスト", "一覧", "list"]) and any(k in text for k in ["表示", "show", "見せ"]):
            return Intent.TABLE, 0.95
        
        # High confidence patterns (specific action keywords)
        if any(k in text for k in ["検索", "search", "探", "さが", "見つけ"]):
            return Intent.SEARCH, 0.9
            
        if any(k in text for k in ["要約", "summary", "まとめ", "概要"]):
            return Intent.SUMMARIZE, 0.9
            
        if any(k in text for k in ["表", "table", "一覧", "リスト"]):
            return Intent.TABLE, 0.9
            
        if any(k in text for k in ["開", "open", "表示", "開く"]):
            return Intent.OPEN, 0.9
            
        # Medium confidence patterns (content-related)
        if any(k in text for k in ["読", "見", "内容", "本文", "全文"]):
            return Intent.READ, 0.7
            
        if any(k in text for k in ["ノート", "note", "メモ", "文書"]):
            # Could be open or read, lean towards read
            return Intent.READ, 0.6
            
        # Low confidence - unclear intent
        if any(k in text for k in ["について", "とは", "って", "どう"]):
            return Intent.COMMENT, 0.5
            
        return Intent.UNKNOWN, 0.0
    
    def _extract_entities(self, text: str, intent: Intent) -> dict[str, Optional[str]]:
        """Extract entities like note names, sections from input."""
        entities = {"query": text, "note": None, "section": None, "vault": None}
        
        # Simple entity extraction - can be enhanced later
        # For now, just preserve the original query
        return entities


# Backward compatibility function
def detect_intent(text: str) -> Intent:
    """Legacy function for backward compatibility."""
    classifier = IntentClassifier()
    result = classifier.classify(text)
    return result.intent
