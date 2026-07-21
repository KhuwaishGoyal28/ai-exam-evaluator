"""
Pure image-processing helpers (no LLM, no storage calls).
Wraps Pillow operations. Each function does exactly one thing.
"""
import base64
import io
from PIL import Image


def load_image_from_bytes(data: bytes) -> Image.Image:
    """Decode raw bytes into a Pillow Image object."""
    return Image.open(io.BytesIO(data)).convert("RGB")


def image_to_base64(image: Image.Image, fmt: str = "JPEG") -> str:
    """Encode a Pillow Image to a base64 string (for Vision API payloads)."""
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def image_to_bytes(image: Image.Image, fmt: str = "JPEG") -> bytes:
    """Encode a Pillow Image back to raw bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, quality=92)
    return buffer.getvalue()


def resize_if_too_large(image: Image.Image, max_dimension: int = 2048) -> Image.Image:
    """
    Downscale image so its longest side is at most max_dimension pixels.
    Returns the original if already within bounds.
    """
    w, h = image.size
    if max(w, h) <= max_dimension:
        return image
    ratio = max_dimension / max(w, h)
    new_size = (int(w * ratio), int(h * ratio))
    return image.resize(new_size, Image.LANCZOS)


def get_image_dimensions(image: Image.Image) -> tuple[int, int]:
    """Return (width, height) of the image."""
    return image.size
