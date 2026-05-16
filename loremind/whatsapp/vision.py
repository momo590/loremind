"""OCR for handwritten notes images — uses Claude Vision (cross-platform).

Falls back to macOS Vision framework if running on macOS and Anthropic key not set.
"""
from __future__ import annotations
import base64
import os
import sys
from pathlib import Path
from typing import Optional


VISION_PROMPT = """This is a photo of handwritten TTRPG session notes from a Game Master.

Extract ALL text you can see. Keep abbreviations and shorthand as-is — the GM will understand them.
Include crossed-out text with ~~strikethrough~~ markup.
Preserve the rough structure (bullets, sections) if visible.

Return only the extracted text, nothing else."""


def extract_text_from_image(image_path: Path) -> Optional[str]:
    """Extract text from a handwritten notes image.

    Uses Claude Vision by default (works cross-platform).
    Falls back to macOS Vision framework if no API key available.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return _extract_via_claude(image_path, api_key)

    if sys.platform == "darwin":
        return _extract_via_macos_vision(image_path)

    return None


def _extract_via_claude(image_path: Path, api_key: str) -> Optional[str]:
    import anthropic

    image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
    suffix = image_path.suffix.lower().lstrip(".")
    media_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "heic": "image/jpeg"}
    media_type = media_type_map.get(suffix, "image/jpeg")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": VISION_PROMPT},
            ],
        }],
    )
    return response.content[0].text.strip() or None


def _extract_via_macos_vision(image_path: Path) -> Optional[str]:
    """macOS Vision framework OCR — no API key needed, runs locally."""
    try:
        import objc  # pyobjc
        from Vision import VNRecognizeTextRequest, VNImageRequestHandler
        from Foundation import NSURL

        url = NSURL.fileURLWithPath_(str(image_path))
        handler = VNImageRequestHandler.alloc().initWithURL_options_(url, {})
        request = VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(1)  # accurate
        handler.performRequests_error_([request], None)

        results = request.results() or []
        texts = [obs.topCandidates_(1)[0].string() for obs in results if obs.topCandidates_(1)]
        return "\n".join(texts) or None
    except ImportError:
        return None
    except Exception:
        return None
