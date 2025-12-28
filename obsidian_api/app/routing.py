from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
from enum import Enum

from .intent import Intent, IntentResult


class Action(str, Enum):
    """Available actions that can be executed."""
    EXECUTE = "execute"           # Execute the intent immediately  
    FALLBACK = "fallback"         # Try alternative intent (e.g., open -> search)
    CLARIFY = "clarify"           # Ask user for clarification
    REJECT = "reject"             # Cannot handle this request


@dataclass(frozen=True)
class RoutingDecision:
    """Result of routing policy decision."""
    action: Action
    target_intent: Intent
    fallback_intent: Optional[Intent] = None
    confidence_threshold: float = 0.0
    reason: Optional[str] = None


@dataclass(frozen=True) 
class RoutingPolicy:
    """Policy class for determining how to handle intent classification results.
    
    Implements Phase 1 logic:
    - High confidence: execute immediately
    - Medium confidence: execute with fallback
    - Low confidence: clarify
    """
    
    # Confidence thresholds
    high_confidence_threshold: float = 0.8
    medium_confidence_threshold: float = 0.5
    
    def decide(self, intent_result: IntentResult) -> RoutingDecision:
        """Decide what action to take based on intent and confidence."""
        intent = intent_result.intent
        confidence = intent_result.confidence
        
        # Handle UNKNOWN intent
        if intent == Intent.UNKNOWN:
            return RoutingDecision(
                action=Action.CLARIFY,
                target_intent=intent,
                reason="Intent could not be determined"
            )
        
        # High confidence - execute immediately
        if confidence >= self.high_confidence_threshold:
            return RoutingDecision(
                action=Action.EXECUTE,
                target_intent=intent,
                confidence_threshold=confidence,
                reason="High confidence execution"
            )
        
        # Medium confidence - execute with potential fallback
        if confidence >= self.medium_confidence_threshold:
            fallback = self._get_fallback_intent(intent)
            return RoutingDecision(
                action=Action.EXECUTE,
                target_intent=intent,
                fallback_intent=fallback,
                confidence_threshold=confidence,
                reason="Medium confidence execution with fallback"
            )
        
        # Low confidence - ask for clarification
        return RoutingDecision(
            action=Action.CLARIFY,
            target_intent=intent,
            confidence_threshold=confidence,
            reason="Low confidence, needs clarification"
        )
    
    def _get_fallback_intent(self, intent: Intent) -> Optional[Intent]:
        """Define fallback intents for each primary intent."""
        fallback_map = {
            Intent.OPEN: Intent.SEARCH,      # open -> search
            Intent.READ: Intent.SEARCH,      # read -> search  
            Intent.SUMMARIZE: Intent.READ,   # summarize -> read
            Intent.COMMENT: Intent.READ,     # comment -> read
            Intent.UPDATE: Intent.READ,      # update -> read
        }
        return fallback_map.get(intent)
    
    def should_attempt_fallback(self, 
                               original_intent: Intent, 
                               execution_failed: bool) -> Optional[Intent]:
        """Determine if fallback should be attempted after execution failure."""
        if not execution_failed:
            return None
            
        return self._get_fallback_intent(original_intent)


@dataclass(frozen=True)
class ClarificationGenerator:
    """Generate clarification questions for ambiguous intents."""
    
    def generate_clarification(self, intent_result: IntentResult) -> dict:
        """Generate a clarification question with options."""
        intent = intent_result.intent
        query = intent_result.entities.get("query", "")
        
        if intent == Intent.UNKNOWN:
            return {
                "question": f"「{query}」について、何をしたいですか？",
                "options": [
                    {"label": "開く", "intent": "open"},
                    {"label": "検索", "intent": "search"},
                    {"label": "読む", "intent": "read"}
                ]
            }
        
        # For low-confidence specific intents, offer alternatives
        base_question = f"「{query}」について"
        
        if intent == Intent.OPEN:
            return {
                "question": f"{base_question}、どちらですか？",
                "options": [
                    {"label": "開く", "intent": "open"},
                    {"label": "検索", "intent": "search"}
                ]
            }
        
        if intent == Intent.READ:
            return {
                "question": f"{base_question}、どちらですか？",
                "options": [
                    {"label": "読む", "intent": "read"},
                    {"label": "要約", "intent": "summarize"}
                ]
            }
        
        # Default fallback
        return {
            "question": f"{base_question}、どうしますか？",
            "options": [
                {"label": "開く", "intent": "open"},
                {"label": "検索", "intent": "search"}
            ]
        }