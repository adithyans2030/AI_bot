import numpy as np

from app.retrieval import cosine_similarity, top_k_chunks


def test_cosine_similarity_identical_vectors():
    v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    matrix = np.array([v, v * 2], dtype=np.float32)
    scores = cosine_similarity(v, matrix)
    assert np.allclose(scores, [1.0, 1.0], atol=1e-5)


def test_cosine_similarity_orthogonal_vectors():
    query = np.array([1.0, 0.0], dtype=np.float32)
    matrix = np.array([[0.0, 1.0]], dtype=np.float32)
    scores = cosine_similarity(query, matrix)
    assert np.allclose(scores, [0.0], atol=1e-5)


def test_top_k_chunks_returns_most_similar_first():
    query = np.array([1.0, 0.0], dtype=np.float32)
    chunk_ids = ["a", "b", "c"]
    chunk_texts = ["about x", "about y", "about z"]
    embeddings = np.array(
        [
            [0.0, 1.0],   # orthogonal -> least similar
            [1.0, 0.01],  # nearly identical -> most similar
            [0.7, 0.7],   # in between
        ],
        dtype=np.float32,
    )
    results = top_k_chunks(query, chunk_ids, chunk_texts, embeddings, k=2)
    assert [r.chunk_id for r in results] == ["b", "c"]


def test_top_k_chunks_empty_embeddings():
    query = np.array([1.0, 0.0], dtype=np.float32)
    results = top_k_chunks(query, [], [], np.zeros((0, 2), dtype=np.float32), k=3)
    assert results == []
