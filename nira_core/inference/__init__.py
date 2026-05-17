"""Inference abstraction layer for Ollama now and llama.cpp later."""

from nira_core.inference.base import InferenceRequest, InferenceResult, TokenAccounting, estimate_tokens
from nira_core.inference.manager import LocalInferenceManager

__all__ = [
    "InferenceRequest",
    "InferenceResult",
    "LocalInferenceManager",
    "TokenAccounting",
    "estimate_tokens",
]
