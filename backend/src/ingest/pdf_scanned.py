"""Scanned PDF adapter — OCR-based extraction for image-only PDFs.

Uses PyMuPDF to render pages to images, then pytesseract for OCR with
bounding box data. Merges OCR tokens into logical lines based on spatial
proximity.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from src.canonical.model import CanonicalDocument, Element, Page
from src.delta.normalize import normalize
from src.ingest.base import FormatAdapter, IngestionError

logger = logging.getLogger(__name__)

# DPI for page rendering — 300 is standard for OCR quality
_RENDER_DPI = 300

# Maximum horizontal gap (in pixels at _RENDER_DPI) to merge words on the same line
_LINE_MERGE_GAP = 20

# Minimum OCR confidence threshold to include a word (0-100 tesseract scale)
_MIN_WORD_CONFIDENCE = 10


def _merge_words_into_lines(words: list[dict]) -> list[dict]:
    """Merge OCR words into logical lines based on vertical overlap and horizontal proximity.

    Words are considered part of the same line if:
    - They vertically overlap (their y-ranges intersect)
    - The horizontal gap between consecutive words is < _LINE_MERGE_GAP pixels

    Returns a list of merged line dicts with keys: text, bbox (x0,y0,x1,y1), confidence.
    """
    if not words:
        return []

    # Sort by top-y then left-x
    sorted_words = sorted(words, key=lambda w: (w["top"], w["left"]))

    lines: list[dict] = []
    current_line: list[dict] = [sorted_words[0]]

    for word in sorted_words[1:]:
        prev = current_line[-1]
        # Check vertical overlap: word and previous are on the same line
        # if their vertical ranges overlap by at least 50%
        prev_mid_y = (prev["top"] + prev["bottom"]) / 2
        word_mid_y = (word["top"] + word["bottom"]) / 2
        prev_height = prev["bottom"] - prev["top"]
        word_height = word["bottom"] - word["top"]
        avg_height = (prev_height + word_height) / 2

        vertical_overlap = abs(prev_mid_y - word_mid_y) < avg_height * 0.6

        # Check horizontal proximity
        h_gap = word["left"] - prev["right"]
        close_enough = h_gap < _LINE_MERGE_GAP

        if vertical_overlap and close_enough:
            current_line.append(word)
        else:
            # Flush current line
            lines.append(_flush_line(current_line))
            current_line = [word]

    # Flush final line
    if current_line:
        lines.append(_flush_line(current_line))

    return lines


def _flush_line(words: list[dict]) -> dict:
    """Combine a list of words into a single line element."""
    text = " ".join(w["text"] for w in words)
    x0 = min(w["left"] for w in words)
    y0 = min(w["top"] for w in words)
    x1 = max(w["right"] for w in words)
    y1 = max(w["bottom"] for w in words)
    avg_conf = sum(w["conf"] for w in words) / len(words)
    return {"text": text, "bbox": (x0, y0, x1, y1), "confidence": avg_conf}


class ScannedPDFAdapter(FormatAdapter):
    """Adapter for scanned (image-only) PDFs using OCR."""

    def can_handle(self, file_path: str) -> bool:
        """Return True for PDF files that lack a text layer (i.e., scanned).

        This adapter is tried AFTER the native adapter, so if we get here
        with a .pdf file, it means the native adapter already declined.
        We still verify it's a valid, openable PDF.
        """
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            return False
        try:
            doc = fitz.open(file_path)
            valid = doc.page_count > 0
            doc.close()
            return valid
        except Exception:
            return False

    def ingest(self, file_path: str, document_id: str, revision: str) -> CanonicalDocument:
        """OCR each page of a scanned PDF and extract elements with confidence scores."""
        path = Path(file_path)
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise IngestionError(f"Failed to open scanned PDF '{path.name}': {e}") from e

        if doc.page_count == 0:
            doc.close()
            raise IngestionError(f"PDF '{path.name}' has no pages.")

        pages: list[Page] = []

        for page_idx, page in enumerate(doc):
            page_number = page_idx + 1
            page_width = page.rect.width
            page_height = page.rect.height

            # Render page to image
            mat = fitz.Matrix(_RENDER_DPI / 72, _RENDER_DPI / 72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Run OCR with word-level bounding boxes
            try:
                ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            except Exception as e:
                raise IngestionError(
                    f"OCR failed on page {page_number} of '{path.name}': {e}"
                ) from e

            # Build word list from OCR output
            words: list[dict] = []
            n_words = len(ocr_data["text"])
            for i in range(n_words):
                text = ocr_data["text"][i].strip()
                conf = float(ocr_data["conf"][i])
                if not text or conf < _MIN_WORD_CONFIDENCE:
                    continue
                words.append({
                    "text": text,
                    "left": ocr_data["left"][i],
                    "top": ocr_data["top"][i],
                    "right": ocr_data["left"][i] + ocr_data["width"][i],
                    "bottom": ocr_data["top"][i] + ocr_data["height"][i],
                    "conf": conf,
                })

            # Merge into lines
            lines = _merge_words_into_lines(words)

            # Calculate page average confidence for warning
            if lines:
                page_avg_conf = sum(ln["confidence"] for ln in lines) / len(lines)
                if page_avg_conf < 50.0:
                    logger.warning(
                        "Low OCR confidence on page %d of '%s': average=%.1f%%",
                        page_number,
                        path.name,
                        page_avg_conf,
                    )

            # Scale factor to convert pixel coords back to PDF points
            scale_x = page_width / pix.width
            scale_y = page_height / pix.height

            elements: list[Element] = []
            for line in lines:
                content = line["text"]
                bbox_px = line["bbox"]
                # Convert pixel bbox to PDF-point bbox
                bbox = (
                    round(bbox_px[0] * scale_x, 2),
                    round(bbox_px[1] * scale_y, 2),
                    round(bbox_px[2] * scale_x, 2),
                    round(bbox_px[3] * scale_y, 2),
                )
                elements.append(
                    Element(
                        id=str(uuid.uuid4()),
                        type="text",  # OCR text is generic; downstream can reclassify
                        content=content,
                        normalized_content=normalize(content),
                        bbox=bbox,
                        page_number=page_number,
                        confidence=round(line["confidence"] / 100.0, 4),
                        source_format="scanned_pdf",
                    )
                )

            pages.append(
                Page(
                    page_number=page_number,
                    width=round(page_width, 2),
                    height=round(page_height, 2),
                    elements=elements,
                )
            )

        doc.close()

        return CanonicalDocument(
            document_id=document_id,
            revision=revision,
            format="scanned_pdf",
            source_filename=path.name,
            ingested_at=datetime.now(timezone.utc),
            pages=pages,
            metadata={},
        )
