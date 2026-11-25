"""Pure-logic tests for prompt construction — no network/model call
(generate_question itself needs a live LLM and is exercised manually; see
README). build_user_prompt() is plain string formatting and fully testable
in isolation."""
from app.question_gen import build_user_prompt
from app.retrieval import ScoredChunk

CHUNK = ScoredChunk(chunk_id="c-1", text="Some unit material.", score=0.9)


def test_omits_asked_block_when_previews_empty():
    prompt = build_user_prompt([CHUNK], "transcript", previously_asked_previews=None)
    assert "already asked" not in prompt.lower()

    prompt_empty_list = build_user_prompt([CHUNK], "transcript", previously_asked_previews=[])
    assert "already asked" not in prompt_empty_list.lower()


def test_includes_asked_block_when_previews_given():
    prompt = build_user_prompt([CHUNK], "transcript", previously_asked_previews=["deletion in BSTs", "search complexity"])
    assert "already asked" in prompt.lower()
    assert "deletion in BSTs" in prompt
    assert "search complexity" in prompt


def test_omits_slide_block_when_slide_text_absent():
    assert "shared slide" not in build_user_prompt([CHUNK], "transcript").lower()
    assert "shared slide" not in build_user_prompt([CHUNK], "transcript", slide_text="   ").lower()


def test_includes_slide_block_when_slide_text_given():
    prompt = build_user_prompt([CHUNK], "transcript", slide_text="Binary Search Trees")
    assert "shared slide" in prompt.lower()
    assert "Binary Search Trees" in prompt


def test_omits_wrap_up_block_by_default():
    assert "wrap-up" not in build_user_prompt([CHUNK], "transcript").lower()


def test_includes_wrap_up_block_when_flagged():
    prompt = build_user_prompt([CHUNK], "transcript", wrap_up=True)
    assert "wrap-up" in prompt.lower()
