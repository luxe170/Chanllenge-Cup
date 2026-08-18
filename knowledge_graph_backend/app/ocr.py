"""Pluggable OCR provider used when a PDF has no extractable text (e.g. scanned resumes).

The default provider is a no-op so the resume pipeline still runs without any
OCR service configured. To plug in a real model, set environment variables:

    OCR_PROVIDER=http                        # currently the only remote kind
    OCR_ENDPOINT=https://api.example.com/ocr # POST target
    OCR_API_KEY=<bearer token, optional>
    OCR_TIMEOUT_SECONDS=30                   # optional, default 30
    OCR_IMAGE_FIELD=image                    # optional multipart field name

The HTTP provider posts the raw image bytes as multipart/form-data under
``OCR_IMAGE_FIELD`` and expects a JSON body containing one of:

    {"text": "..."}          or
    {"data": {"text": "..."}} or
    {"result": {"text": "..."}}

Any provider can be substituted by calling :func:`set_ocr_provider` from tests
or a wiring module.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Callable, Protocol
from urllib import request as urllib_request
from urllib.error import URLError


logger = logging.getLogger(__name__)


class OcrError(RuntimeError):
    """Raised when an OCR call fails or the provider is not configured."""


class OcrProvider(Protocol):
    """Turn an image (usually one rendered PDF page) into text."""

    name: str
    available: bool

    def recognize(self, image: bytes, mime: str = "image/png") -> str: ...


class NullOcrProvider:
    """Default provider — reports itself unavailable so callers can degrade."""

    name = "null"
    available = False

    def recognize(self, image: bytes, mime: str = "image/png") -> str:
        raise OcrError(
            "OCR provider not configured. Set OCR_PROVIDER and OCR_ENDPOINT to enable OCR."
        )


class CallableOcrProvider:
    """Wrap an arbitrary function; useful for tests and quick experiments."""

    name = "callable"
    available = True

    def __init__(self, func: Callable[[bytes, str], str], *, name: str = "callable"):
        self._func = func
        self.name = name

    def recognize(self, image: bytes, mime: str = "image/png") -> str:
        return self._func(image, mime)


class HttpOcrProvider:
    """Send an image to a JSON HTTP endpoint and read its text back.

    The endpoint contract is deliberately simple so any Chinese OCR SaaS
    (Baidu, Tencent, Aliyun, self-hosted PaddleOCR/RapidOCR service) can be
    wrapped behind one thin adapter layer without pulling in a vendor SDK.
    """

    name = "http"
    available = True

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        image_field: str = "image",
    ) -> None:
        if not endpoint:
            raise ValueError("OCR endpoint is required")
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout = timeout
        self.image_field = image_field

    def recognize(self, image: bytes, mime: str = "image/png") -> str:
        boundary = "----ClaudeOcrBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{self.image_field}"; filename="page.png"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8") + image + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib_request.Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib_request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
        except URLError as exc:
            raise OcrError(f"OCR request failed: {exc}") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OcrError(f"OCR response was not valid JSON: {exc}") from exc
        return _extract_text_from_response(payload)


def _extract_text_from_response(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "content", "result_text", "recognized_text"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        for key in ("data", "result", "response"):
            nested = payload.get(key)
            if isinstance(nested, (dict, list, str)):
                text = _extract_text_from_response(nested)
                if text:
                    return text
    if isinstance(payload, list):
        parts = [_extract_text_from_response(item) for item in payload]
        return "\n".join(part for part in parts if part)
    return ""


_provider: OcrProvider | None = None


def get_ocr_provider() -> OcrProvider:
    """Return the process-wide OCR provider, building it from env on first use."""

    global _provider
    if _provider is not None:
        return _provider
    kind = (os.getenv("OCR_PROVIDER") or "").strip().lower()
    if kind in ("", "null", "none", "off"):
        _provider = NullOcrProvider()
        return _provider
    if kind == "http":
        endpoint = os.getenv("OCR_ENDPOINT", "").strip()
        if not endpoint:
            logger.warning("OCR_PROVIDER=http but OCR_ENDPOINT is empty; falling back to no-op provider")
            _provider = NullOcrProvider()
            return _provider
        _provider = HttpOcrProvider(
            endpoint=endpoint,
            api_key=os.getenv("OCR_API_KEY") or None,
            timeout=float(os.getenv("OCR_TIMEOUT_SECONDS", "30")),
            image_field=os.getenv("OCR_IMAGE_FIELD", "image"),
        )
        return _provider
    logger.warning("Unknown OCR_PROVIDER=%s; falling back to no-op provider", kind)
    _provider = NullOcrProvider()
    return _provider


def set_ocr_provider(provider: OcrProvider | None) -> None:
    """Override the process provider. Pass ``None`` to reset to env-driven lookup."""

    global _provider
    _provider = provider
