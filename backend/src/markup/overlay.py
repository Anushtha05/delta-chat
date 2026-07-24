"""Delta markup overlay — annotates source PDFs with colored change highlights.

Draws colored rectangles over detected changes:
- Red: removed elements
- Green: added elements
- Amber/Orange: modified elements

Only implemented for native_pdf and scanned_pdf. DWG markup is out of scope.
"""

import logging
from io import BytesIO

import fitz  # PyMuPDF

from src.canonical.model import CanonicalDocument
from src.delta.model import DeltaRecord

logger = logging.getLogger(__name__)

# Colors (R, G, B) normalized 0-1
_COLOR_REMOVED = (0.9, 0.2, 0.2)    # Red
_COLOR_ADDED = (0.1, 0.75, 0.4)     # Green
_COLOR_MODIFIED = (0.95, 0.65, 0.1)  # Amber

_COLOR_MAP = {
    "removed": _COLOR_REMOVED,
    "added": _COLOR_ADDED,
    "modified": _COLOR_MODIFIED,
}


def render_markup(
    document: CanonicalDocument,
    delta_records: list[DeltaRecord],
    source_pdf_path: str,
    side: str = "a",
) -> bytes:
    """Render an annotated PDF with delta highlights overlaid on the source.

    Args:
        document: The CanonicalDocument for the source being annotated.
        delta_records: All DeltaRecords from the comparison.
        source_pdf_path: Path to the original PDF file on disk.
        side: "a" (base document) or "b" (revised document).

    Returns:
        Annotated PDF as bytes.

    Note:
        Only supports native_pdf and scanned_pdf formats.
        DWG/DXF overlay is not implemented (would require CAD rendering).
    """
    if document.format == "dwg":
        raise ValueError(
            "DWG markup overlay is not supported. "
            "Only PDF documents (native or scanned) can be annotated."
        )

    doc = fitz.open(source_pdf_path)

    # Filter records relevant to this document side
    relevant_records = []
    for record in delta_records:
        if side == "a":
            # For doc A: show removed (was here) and modified (old location)
            if record.change_type in ("removed", "modified") and record.bbox_a:
                relevant_records.append((record, record.bbox_a))
        else:
            # For doc B: show added (new here) and modified (new location)
            if record.change_type in ("added", "modified") and record.bbox_b:
                relevant_records.append((record, record.bbox_b))

    annotations_drawn = 0

    for record, bbox in relevant_records:
        page_idx = record.page - 1  # 0-indexed
        if page_idx < 0 or page_idx >= doc.page_count:
            continue

        page = doc[page_idx]
        x0, y0, x1, y1 = bbox

        # Ensure bbox is valid and within page bounds
        if x0 >= x1 or y0 >= y1:
            continue

        color = _COLOR_MAP.get(record.change_type, _COLOR_MODIFIED)

        # Draw a semi-transparent highlight rectangle
        rect = fitz.Rect(x0, y0, x1, y1)

        # Add highlight annotation
        annot = page.add_rect_annot(rect)
        annot.set_colors(stroke=color)
        annot.set_border(width=1.5)
        annot.set_opacity(0.4)
        annot.set_info(
            title=record.change_type.upper(),
            content=f"{record.change_id[:8]}: {record.description[:80]}",
        )
        annot.update()
        annotations_drawn += 1

    logger.info(
        "Markup overlay: drew %d annotations on %s (side=%s)",
        annotations_drawn, document.document_id, side,
    )

    # Save to bytes
    output = BytesIO()
    doc.save(output)
    doc.close()

    return output.getvalue()
