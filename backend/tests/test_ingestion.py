from app.ingestion import chunk_text


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_chunk_text_single_short_paragraph_becomes_one_chunk():
    text = " ".join(["word"] * 50)
    chunks = chunk_text(text, min_words=150, max_words=300)
    assert len(chunks) == 1
    assert len(chunks[0].split()) == 50


def test_chunk_text_respects_max_words():
    # Three paragraphs of 120 words each -> should not exceed max_words=300 per chunk.
    para = " ".join(["word"] * 120)
    text = "\n\n".join([para, para, para])
    chunks = chunk_text(text, min_words=150, max_words=300)
    for c in chunks:
        assert len(c.split()) <= 300


def test_chunk_text_packs_until_min_words_reached():
    # Many small paragraphs should be packed together rather than left as
    # separate tiny chunks, until min_words is reached.
    para = " ".join(["word"] * 20)
    text = "\n\n".join([para] * 10)  # 200 words total
    chunks = chunk_text(text, min_words=150, max_words=300)
    assert len(chunks) == 1
    assert len(chunks[0].split()) == 200


def test_chunk_text_hard_splits_oversized_paragraph():
    para = " ".join(["word"] * 700)
    chunks = chunk_text(para, min_words=150, max_words=300)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.split()) <= 300 + 150  # allows a merged small tail
