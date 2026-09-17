"""Unit material ingestion: chunking + local embedding.

Chunking is a pure function (no model needed, fast to test). Embedding lazily
loads a local sentence-transformers model on first use so importing this
module never triggers a model download.
"""
from __future__ import annotations

from typing import List

import numpy as np

from . import config

_embedder = None


def chunk_text(
    text: str,
    min_words: int = config.CHUNK_MIN_WORDS,
    max_words: int = config.CHUNK_MAX_WORDS,
) -> List[str]:
    """Split plain text into ~min_words-max_words passages.

    Splits on paragraph boundaries first, then greedily packs paragraphs into
    chunks up to max_words, only closing a chunk early once it has reached
    min_words. A single paragraph longer than max_words is hard-split on
    word boundaries so no chunk ever exceeds max_words by much.
    """
    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n")]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return []

    chunks: List[str] = []
    current_words: List[str] = []

    def flush():
        if current_words:
            chunks.append(" ".join(current_words))

    for para in paragraphs:
        para_words = para.split()

        # Hard-split any paragraph that alone exceeds max_words.
        if len(para_words) > max_words:
            flush()
            current_words = []
            for i in range(0, len(para_words), max_words):
                piece = para_words[i : i + max_words]
                if len(piece) < min_words and chunks:
                    # Too small a tail piece on its own: merge into previous.
                    chunks[-1] = chunks[-1] + " " + " ".join(piece)
                else:
                    chunks.append(" ".join(piece))
            continue

        if len(current_words) + len(para_words) > max_words and current_words:
            flush()
            current_words = list(para_words)
        else:
            current_words.extend(para_words)

        if len(current_words) >= min_words and len(current_words) >= max_words:
            flush()
            current_words = []

    flush()
    return [c for c in chunks if c]


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(config.EMBEDDING_MODEL)
    return _embedder


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a list of strings, returns an (N, dim) float32 array."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = get_embedder()
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)


def embed_text(text: str) -> np.ndarray:
    """Embed a single string, returns a (dim,) float32 array."""
    return embed_texts([text])[0]
