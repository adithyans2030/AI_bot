"""In-memory cosine-similarity search over a unit's stored chunks.

Deliberately not a vector DB — a unit's notes are a few thousand words, so a
numpy matmul over stored chunk embeddings is more than fast enough for v1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from . import config


@dataclass
class ScoredChunk:
    chunk_id: str
    text: str
    score: float


def cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """query: (dim,), matrix: (N, dim) -> (N,) similarity scores."""
    if matrix.shape[0] == 0:
        return np.zeros((0,), dtype=np.float32)
    query_norm = np.linalg.norm(query)
    matrix_norms = np.linalg.norm(matrix, axis=1)
    denom = matrix_norms * query_norm
    denom[denom == 0] = 1e-8
    return (matrix @ query) / denom


def top_k_chunks(
    query_vec: np.ndarray,
    chunk_ids: List[str],
    chunk_texts: List[str],
    embeddings: np.ndarray,
    k: int = config.RETRIEVAL_TOP_K,
) -> List[ScoredChunk]:
    """Return the k chunks whose embeddings are closest to query_vec."""
    if embeddings.shape[0] == 0:
        return []
    scores = cosine_similarity(query_vec, embeddings)
    k = min(k, len(scores))
    top_indices = np.argsort(-scores)[:k]
    return [
        ScoredChunk(chunk_id=chunk_ids[i], text=chunk_texts[i], score=float(scores[i]))
        for i in top_indices
    ]
