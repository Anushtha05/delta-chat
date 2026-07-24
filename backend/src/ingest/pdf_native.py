"""Native PDF adapter — extracts text elements from PDFs with an embedded text layer.

Detection heuristic: A PDF is "native" if at least one page has extractable text
covering a meaningful area (>5% of total text runs have non-empty content). If no
page qualifies, the PDF is treated as scanned and this adapter declines.
"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

from src.canonical.model import CanonicalDocument, Element, Page
from src.delta.normalize import normalize
from src.ingest.base import FormatAdapter, IngestionError

# ─── Element type classification heuristics ───────────────────────────────────

# Matches numbers with optional decimal and unit suffixes (e.g., "3.5 mm", "100 PSI", "DN50")
_RE_TECHNICAL_VALUE = re.compile(
    r"^\s*[\d.,]+\s*(?:mm|cm|m|in|ft|psi|bar|kpa|mpa|°[cf]|dn\d*|nb|"
    r"kg|lb|l/s|m/s|gpm|rpm|kw|hp|mw|btu|cfm|m³/h|°)\s*$",
    re.IGNORECASE,
)

# Matches dimension-like patterns (e.g., "1500 x 2000", "Ø50", "R25")
_RE_DIMENSION = re.compile(
    r"^\s*(?:Ø|ø|R|r)?\s*[\d.,]+\s*(?:x|×|X)\s*[\d.,]+|^\s*(?:Ø|ø|R|r)\s*[\d.,]+",
)

# Equipment tags: short all-caps identifiers (e.g., "XV-100", "P-101A", "TIC-302")
_RE_EQUIPMENT = re.compile(r"^[A-Z]{1,4}[-/]?\d{2,5}[A-Z]?$")

# Instrument tags (ISA standard): FIC, TT, LIC, PT followed by dash and number
_RE_INSTRUMENT = re.compile(r"^[A-Z]{2,4}-\d{2,5}[A-Z]?$")

# Notes: lines starting with "NOTE", "N.B.", numbered notes
_RE_NOTE = re.compile(r"^\s*(?:NOTE|N\.?B\.?|NOTES?:|\d+\.\s)", re.IGNORECASE)


def _classify_element(text: str, bbox: tuple, page_width: float, page_height: float) -> str:
    """Classify an extracted text element into a semantic type.

    Heuristics applied in priority order:
    1. Technical value (number + unit)
    2. Dimension (measurement pattern)
    3. Equipment tag (short all-caps with number)
    4. Instrument tag (ISA-style)
    5. Note (starts with NOTE or similar)
    6. Default: text
    """
    stripped = text.strip()

    if _RE_TECHNICAL_VALUE.match(stripped):
        return "technical_value"
    if _RE_DIMENSION.match(stripped):
        return "dimension"
    if _RE_INSTRUMENT.match(stripped):
        return "instrument"
    if _RE_EQUIPMENT.match(stripped):
        return "equipment"
    if _RE_NOTE.match(stripped):
        return "note"

    return "text"


def _is_native_pdf(doc: fitz.Document) -> bool:
    """Check if the PDF has a meaningful text layer.

    A PDF qualifies as native if at least one page has >5 extractable
    text spans (blocks with non-whitespace content). This filters out
    PDFs that are purely scanned images.
    """
    for page in doc:
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        text_span_count = 0
        for block in blocks:
            if block.get("type") == 0:  # text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            text_span_count += 1
        if text_span_count > 5:
            return True
    return False


class NativePDFAdapter(FormatAdapter):
    """Adapter for PDFs with embedded text layers (non-scanned)."""

    def can_handle(self, file_path: str) -> bool:
        """Return True if file is a PDF with extractable text."""
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            return False
        try:
            doc = fitz.open(file_path)
            result = _is_native_pdf(doc)
            doc.close()
            return result
        except Exception:
            return False

    def ingest(self, file_path: str, document_id: str, revision: str) -> CanonicalDocument:
        """Extract elements from a native PDF using PyMuPDF."""
        path = Path(file_path)
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise IngestionError(f"Failed to open PDF '{path.name}': {e}") from e

        if doc.page_count == 0:
            doc.close()
            raise IngestionError(f"PDF '{path.name}' has no pages.")

        pages: list[Page] = []

        for page_idx, page in enumerate(doc):
            page_number = page_idx + 1
            page_width = page.rect.width
            page_height = page.rect.height
            elements: list[Element] = []

            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            for block in blocks:
                if block.get("type") != 0:  # skip image blocks
                    continue
                for line in block.get("lines", []):
                    # Merge all spans in a line into one element
                    line_text = ""
                    x0 = float("inf")
                    y0 = float("inf")
                    x1 = float("-inf")
                    y1 = float("-inf")

                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        if not span_text.strip():
                            continue
                        line_text += span_text
                        bbox = span.get("bbox", (0, 0, 0, 0))
                        x0 = min(x0, bbox[0])
                        y0 = min(y0, bbox[1])
                        x1 = max(x1, bbox[2])
                        y1 = max(y1, bbox[3])

                    if not line_text.strip():
                        continue

                    content = line_text.strip()
                    elem_type = _classify_element(content, (x0, y0, x1, y1), page_width, page_height)

                    elements.append(
                        Element(
                            id=str(uuid.uuid4()),
                            type=elem_type,
                            content=content,
                            normalized_content=normalize(content),
                            bbox=(round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)),
                            page_number=page_number,
                            confidence=1.0,  # native text is fully reliable
                            source_format="native_pdf",
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
            format="native_pdf",
            source_filename=path.name,
            ingested_at=datetime.now(timezone.utc),
            pages=pages,
            metadata={},
        )
