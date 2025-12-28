from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

from .intent import Intent, IntentResult

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LLMIntentRequest(BaseModel):
    """Schema for LLM intent classification request."""
    intent: str = Field(..., description="Classified intent: open, search, read, summarize, comment, update, table, unknown")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0)
    entities: dict[str, Optional[str]] = Field(
        ..., 
        description="Extracted entities",
        example={"query": "部品を開いて", "note": "部品", "section": None, "vault": None}
    )
    reasoning: str = Field(..., description="Brief explanation for the classification")


@dataclass(frozen=True)
class LLMClassificationMetrics:
    """Metrics for LLM classification performance."""
    request_time: float
    response_time: float
    total_latency_ms: float
    token_usage: Optional[dict] = None
    model_used: str = ""
    success: bool = True
    error_message: Optional[str] = None


@dataclass(frozen=True)
class LLMIntentClassifier:
    """LLM-based intent classifier using OpenAI API.
    
    Provides more sophisticated intent classification with entity extraction
    and natural language understanding.
    """
    
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 200
    timeout: float = 10.0
    
    def classify(self, text: str) -> tuple[IntentResult, LLMClassificationMetrics]:
        """Classify user input using LLM and return result with metrics."""
        start_time = time.time()
        
        if not self._is_enabled():
            # Fallback to rule-based classifier
            from .intent import IntentClassifier
            rule_classifier = IntentClassifier()
            result = rule_classifier.classify(text)
            
            metrics = LLMClassificationMetrics(
                request_time=start_time,
                response_time=time.time(),
                total_latency_ms=0,
                model_used="rule-based-fallback",
                success=True
            )
            return result, metrics
        
        try:
            client = OpenAI(
                api_key=os.environ["OPENAI_API_KEY"],
                timeout=self.timeout
            )
            
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(text)
            
            request_time = time.time()
            
            response = client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=LLMIntentRequest,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            response_time = time.time()
            
            if response.choices[0].parsed:
                llm_result = response.choices[0].parsed
                intent_result = self._convert_to_intent_result(llm_result, text)
                
                metrics = LLMClassificationMetrics(
                    request_time=request_time,
                    response_time=response_time,
                    total_latency_ms=(response_time - start_time) * 1000,
                    token_usage=response.usage.model_dump() if response.usage else None,
                    model_used=self.model,
                    success=True
                )
                
                return intent_result, metrics
            else:
                raise ValueError("Failed to parse LLM response")
                
        except Exception as e:
            # Fallback to rule-based classifier
            from .intent import IntentClassifier
            rule_classifier = IntentClassifier()
            result = rule_classifier.classify(text)
            
            metrics = LLMClassificationMetrics(
                request_time=start_time,
                response_time=time.time(),
                total_latency_ms=(time.time() - start_time) * 1000,
                model_used="rule-based-fallback",
                success=False,
                error_message=str(e)
            )
            
            return result, metrics
    
    def _is_enabled(self) -> bool:
        """Check if LLM classification is enabled."""
        return (
            os.environ.get("ENABLE_LLM_CLASSIFIER", "").strip() == "1"
            and os.environ.get("OPENAI_API_KEY", "").strip() != ""
            and OpenAI is not None
        )
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for intent classification."""
        return """You are an intent classifier for an Obsidian Vault API assistant.

Your task is to analyze user queries and classify them into the following intents:
- open: User wants to open/view a specific note or file
- search: User wants to search for notes/content
- read: User wants to read the content of a note
- summarize: User wants a summary of note content
- comment: User wants explanation, comparison, or analysis
- update: User wants to add/modify content (analysis only, no actual writing)
- table: User wants to extract tables from content
- unknown: Intent cannot be determined

For each classification:
1. Determine the most likely intent
2. Assign confidence (0.0-1.0) based on clarity of the request
3. Extract key entities: note names, sections, specific content
4. Provide brief reasoning

Examples:
- "部品を開いて" → intent: open, note: "部品"
- "部品 を開いて" → intent: open, note: "部品" 
- "部品について検索" → intent: search, note: "部品"
- "部品ケース１の内容を見せて" → intent: read, note: "部品ケース１"

Focus on user's actual intent, ignoring grammatical variations or spacing issues."""

    def _build_user_prompt(self, text: str) -> str:
        """Build user prompt with the input text."""
        return f"Classify this user query: \"{text}\""
    
    def _convert_to_intent_result(self, llm_result: LLMIntentRequest, original_text: str) -> IntentResult:
        """Convert LLM result to IntentResult."""
        try:
            intent = Intent(llm_result.intent)
        except ValueError:
            intent = Intent.UNKNOWN
        
        # Ensure entities contain the original query
        entities = llm_result.entities.copy()
        entities["query"] = original_text
        
        return IntentResult(
            intent=intent,
            confidence=llm_result.confidence,
            entities=entities
        )