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


def test_top_k_chunks_applies_soft_penalty_to_asked_chunks():
    query = np.array([1.0, 0.0], dtype=np.float32)
    chunk_ids = ["a", "b", "c"]
    chunk_texts = ["about a", "about b", "about c"]
    embeddings = np.array(
        [
            [1.0, 0.01],  # "a": nearly identical to query, highest raw score
            [1.0, 0.3],   # "b": clearly second-best, unasked
            [0.0, 1.0],   # "c": orthogonal, lowest
        ],
        dtype=np.float32,
    )

    # Without any penalty, "a" is unambiguously #1.
    baseline = top_k_chunks(query, chunk_ids, chunk_texts, embeddings, k=1)
    assert baseline[0].chunk_id == "a"

    # A large-enough penalty on "a" (already asked) drops it behind "b" —
    # the unasked chunk wins even though its raw score is lower.
    penalized = top_k_chunks(
        query, chunk_ids, chunk_texts, embeddings, k=1, asked_chunk_ids={"a"}, penalty=0.05
    )
    assert penalized[0].chunk_id == "b"

    # A penalty "a" can still survive keeps it on top — this must be a
    # soft nudge, never a hard exclusion.
    small_penalty = top_k_chunks(
        query, chunk_ids, chunk_texts, embeddings, k=1, asked_chunk_ids={"a"}, penalty=0.01
    )
    assert small_penalty[0].chunk_id == "a"


def test_top_k_chunks_no_penalty_when_asked_chunk_ids_absent():
    query = np.array([1.0, 0.0], dtype=np.float32)
    chunk_ids = ["a", "b"]
    chunk_texts = ["about a", "about b"]
    embeddings = np.array([[1.0, 0.01], [1.0, 0.3]], dtype=np.float32)

    assert top_k_chunks(query, chunk_ids, chunk_texts, embeddings, k=1)[0].chunk_id == "a"
    assert top_k_chunks(query, chunk_ids, chunk_texts, embeddings, k=1, asked_chunk_ids=None)[0].chunk_id == "a"
    assert top_k_chunks(query, chunk_ids, chunk_texts, embeddings, k=1, asked_chunk_ids=set())[0].chunk_id == "a"
