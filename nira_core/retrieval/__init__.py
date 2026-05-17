"""Retrieval layer with BGE embeddings and reranking fallbacks."""

from nira_core.retrieval.embedding import EmbeddingProvider
from nira_core.retrieval.pipeline import RetrievalPipeline, RetrievalResult
from nira_core.retrieval.reranker import BGEReranker

__all__ = ["BGEReranker", "EmbeddingProvider", "RetrievalPipeline", "RetrievalResult"]
