"""FlowGuard Tables: local operations-quality analysis."""

from .analyzer import analyze_records
from .classifier import IntentClassifier

__all__ = ["IntentClassifier", "analyze_records"]
