from __future__ import annotations

import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Optional

from .intent import IntentResult, IntentClassifier
from .llm_classifier import LLMIntentClassifier, LLMClassificationMetrics


class ClassifierType(str, Enum):
    RULE_BASED = "rule_based"
    LLM_BASED = "llm_based"
    AUTO = "auto"


class ClassificationMetrics(Protocol):
    """Protocol for classification metrics."""
    request_time: float
    response_time: float
    total_latency_ms: float
    success: bool
    model_used: str
    error_message: Optional[str]


@dataclass
class RuleBasedMetrics:
    """Metrics for rule-based classification."""
    request_time: float
    response_time: float
    total_latency_ms: float
    success: bool = True
    model_used: str = "rule-based"
    error_message: Optional[str] = None


class UnifiedIntentClassifier:
    """Unified classifier that can switch between rule-based and LLM-based classification.
    
    Supports A/B testing and automatic fallback strategies.
    """
    
    def __init__(self, 
                 classifier_type: ClassifierType = ClassifierType.AUTO,
                 llm_model: str = "gpt-4o-mini",
                 fallback_enabled: bool = True):
        self.classifier_type = classifier_type
        self.llm_model = llm_model
        self.fallback_enabled = fallback_enabled
        
        # Initialize classifiers
        self.rule_classifier = IntentClassifier()
        self.llm_classifier = LLMIntentClassifier(model=llm_model)
        
    def classify(self, text: str) -> tuple[IntentResult, ClassificationMetrics]:
        """Classify using the configured strategy."""
        
        if self.classifier_type == ClassifierType.RULE_BASED:
            return self._classify_with_rules(text)
        
        elif self.classifier_type == ClassifierType.LLM_BASED:
            return self._classify_with_llm(text)
        
        elif self.classifier_type == ClassifierType.AUTO:
            return self._classify_auto(text)
        
        else:
            # Default to rule-based
            return self._classify_with_rules(text)
    
    def _classify_with_rules(self, text: str) -> tuple[IntentResult, ClassificationMetrics]:
        """Classify using rule-based method."""
        start_time = time.time()
        
        result = self.rule_classifier.classify(text)
        
        end_time = time.time()
        metrics = RuleBasedMetrics(
            request_time=start_time,
            response_time=end_time,
            total_latency_ms=(end_time - start_time) * 1000
        )
        
        return result, metrics
    
    def _classify_with_llm(self, text: str) -> tuple[IntentResult, ClassificationMetrics]:
        """Classify using LLM method with optional fallback."""
        result, llm_metrics = self.llm_classifier.classify(text)
        
        # If LLM failed and fallback is enabled, try rule-based
        if not llm_metrics.success and self.fallback_enabled:
            rule_result, rule_metrics = self._classify_with_rules(text)
            
            # Create combined metrics showing fallback occurred
            combined_metrics = LLMClassificationMetrics(
                request_time=llm_metrics.request_time,
                response_time=rule_metrics.response_time,
                total_latency_ms=llm_metrics.total_latency_ms + rule_metrics.total_latency_ms,
                token_usage=llm_metrics.token_usage,
                model_used=f"{llm_metrics.model_used} -> {rule_metrics.model_used}",
                success=True,
                error_message=f"LLM failed ({llm_metrics.error_message}), used fallback"
            )
            
            return rule_result, combined_metrics
        
        return result, llm_metrics
    
    def _classify_auto(self, text: str) -> tuple[IntentResult, ClassificationMetrics]:
        """Auto-select classification method based on configuration and context."""
        
        # Check if LLM is available and enabled
        if self._should_use_llm(text):
            return self._classify_with_llm(text)
        else:
            return self._classify_with_rules(text)
    
    def _should_use_llm(self, text: str) -> bool:
        """Determine if LLM should be used based on various factors."""
        
        # Check if LLM is enabled
        if not self._is_llm_enabled():
            return False
        
        # Use LLM for complex queries (multiple words, ambiguous patterns)
        words = text.split()
        
        # Simple single-word queries might not benefit from LLM
        if len(words) == 1 and len(text) < 5:
            return False
        
        # Use LLM for complex queries that likely need natural language understanding
        complex_patterns = [
            "について", "とは", "どう", "なぜ", "なに", "どこ", "いつ",
            "比較", "違い", "説明", "教えて", "わからない"
        ]
        
        if any(pattern in text for pattern in complex_patterns):
            return True
        
        # Use LLM for multi-word queries that might have spacing issues
        if len(words) > 2:
            return True
        
        # Default to rule-based for simple cases
        return False
    
    def _is_llm_enabled(self) -> bool:
        """Check if LLM classification is available."""
        return (
            os.environ.get("ENABLE_LLM_CLASSIFIER", "").strip() == "1"
            and os.environ.get("OPENAI_API_KEY", "").strip() != ""
        )


def create_classifier(classifier_type: Optional[str] = None) -> UnifiedIntentClassifier:
    """Factory function to create appropriate classifier based on configuration."""
    
    # Get classifier type from environment or parameter
    if classifier_type is None:
        classifier_type = os.environ.get("CLASSIFIER_TYPE", "auto")
    
    try:
        classifier_enum = ClassifierType(classifier_type.lower())
    except ValueError:
        classifier_enum = ClassifierType.AUTO
    
    # Get LLM model from environment
    llm_model = os.environ.get("LLM_CLASSIFIER_MODEL", "gpt-4o-mini")
    
    # Check if fallback is enabled
    fallback_enabled = os.environ.get("ENABLE_CLASSIFIER_FALLBACK", "1").strip() == "1"
    
    return UnifiedIntentClassifier(
        classifier_type=classifier_enum,
        llm_model=llm_model,
        fallback_enabled=fallback_enabled
    )