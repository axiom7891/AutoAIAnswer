from __future__ import annotations

import io
import threading


class OcrTextReader:
    """Lazy RapidOCR wrapper; returns an empty string when OCR is unavailable."""

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    def __call__(self, png_bytes: bytes) -> str:
        try:
            import numpy as np
            from PIL import Image
            from rapidocr_onnxruntime import RapidOCR
        except Exception:
            return ""
        try:
            with self._lock:
                if self._engine is None:
                    self._engine = RapidOCR()
                with Image.open(io.BytesIO(png_bytes)) as image:
                    image = image.convert("RGB")
                    if image.width > 1800:
                        image.thumbnail((1800, 1800))
                    pixels = np.asarray(image)[:, :, ::-1]
                result, _elapse = self._engine(pixels)
        except Exception:
            return ""
        if not result:
            return ""
        lines: list[str] = []
        for item in result:
            if len(item) < 3:
                continue
            try:
                confidence = float(item[2])
            except (TypeError, ValueError):
                confidence = 0.0
            text = str(item[1]).strip()
            if text and confidence >= 0.45:
                lines.append(text)
        return "\n".join(lines)
