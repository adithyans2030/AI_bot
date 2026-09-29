import base64
import io

from PIL import Image

from app.slide_vision import (
    _as_data_url,
    _decode_to_bytes,
    _parse_response,
    frame_thumbnail,
    thumbnail_diff,
)


def _solid_color_frame(color: tuple[int, int, int], data_url: bool = False) -> str:
    image = Image.new("RGB", (64, 64), color=color)
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}" if data_url else b64


def test_frame_thumbnail_valid_image():
    thumb = frame_thumbnail(_solid_color_frame((10, 10, 10)))
    assert thumb is not None
    assert thumb.shape == (16, 16)
    assert 0.0 <= thumb.min() and thumb.max() <= 1.0


def test_frame_thumbnail_handles_data_url_prefix():
    thumb_raw = frame_thumbnail(_solid_color_frame((200, 50, 50), data_url=False))
    thumb_data_url = frame_thumbnail(_solid_color_frame((200, 50, 50), data_url=True))
    assert thumb_raw is not None and thumb_data_url is not None
    assert thumb_raw.shape == thumb_data_url.shape


def test_frame_thumbnail_garbage_input_returns_none():
    assert frame_thumbnail("not-valid-base64-image-data") is None
    assert frame_thumbnail("") is None


def test_thumbnail_diff_identical_is_near_zero():
    a = frame_thumbnail(_solid_color_frame((128, 128, 128)))
    b = frame_thumbnail(_solid_color_frame((128, 128, 128)))
    assert thumbnail_diff(a, b) < 0.01


def test_thumbnail_diff_very_different_is_large():
    black = frame_thumbnail(_solid_color_frame((0, 0, 0)))
    white = frame_thumbnail(_solid_color_frame((255, 255, 255)))
    assert thumbnail_diff(black, white) > 0.5


def test_thumbnail_diff_missing_side_is_maximal():
    a = frame_thumbnail(_solid_color_frame((0, 0, 0)))
    assert thumbnail_diff(a, None) == 1.0
    assert thumbnail_diff(None, a) == 1.0
    assert thumbnail_diff(None, None) == 1.0


def test_parse_response_high_confidence():
    text = "TITLE: Binary Search Trees\nTEXT: Deletion with two children\nCONFIDENCE: HIGH"
    result = _parse_response(text)
    assert result == {
        "slide_title": "Binary Search Trees",
        "key_text": "Deletion with two children",
        "confidence": "high",
    }


def test_parse_response_low_confidence():
    text = "TITLE: NONE\nTEXT: NONE\nCONFIDENCE: LOW"
    result = _parse_response(text)
    assert result["confidence"] == "low"
    assert result["slide_title"] is None
    assert result["key_text"] is None


def test_parse_response_unparseable_defaults_to_low_confidence():
    # No model output should ever be trusted enough to feed into matching
    # unless it's unambiguously well-formed and HIGH.
    assert _parse_response("I'm not sure what this image shows.")["confidence"] == "low"
    assert _parse_response("")["confidence"] == "low"
    assert _parse_response("TITLE: Something\nCONFIDENCE: MAYBE")["confidence"] == "low"


def test_as_data_url_idempotent_on_prefixed_input():
    raw = "abc123=="
    assert _as_data_url(raw) == "data:image/jpeg;base64,abc123=="
    already_prefixed = "data:image/jpeg;base64,abc123=="
    assert _as_data_url(already_prefixed) == already_prefixed


def test_decode_to_bytes_roundtrip():
    original = b"hello world"
    b64 = base64.b64encode(original).decode("ascii")
    assert _decode_to_bytes(b64) == original
    assert _decode_to_bytes(f"data:image/jpeg;base64,{b64}") == original
