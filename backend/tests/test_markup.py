"""Tests for the delta markup overlay (Phase 11 bonus).

Verifies that the annotated PDF has more annotations than the original.
"""

import os
import tempfile
import uuid
from datetime import datetime, timezone

import fitz
import pytest

os.environ["TESTING"] = "true"

from src.canonical.model import CanonicalDocument, Element, Page
from src.delta.model import DeltaRecord
from src.delta.normalize import normalize
from src.markup.overlay import render_markup


def _make_doc_and_pdf():
    """Create a CanonicalDocument and matching PDF file."""
    elements = [
        Element(id=str(uuid.uuid4()), type="text", content="Old Pressure: 45 barg",
                normalized_content=normalize("Old Pressure: 45 barg"),
                bbox=(50.0, 100.0, 250.0, 115.0), page_number=1,
                confidence=1.0, source_format="native_pdf"),
        Element(id=str(uuid.uuid4()), type="text", content="Equipment Tag: 26-KC-501",
                normalized_content=normalize("Equipment Tag: 26-KC-501"),
                bbox=(50.0, 130.0, 280.0, 145.0), page_number=1,
                confidence=1.0, source_format="native_pdf"),
    ]
    doc = CanonicalDocument(
        document_id="MARKUP-TEST", revision="A", format="native_pdf",
        source_filename="test.pdf", ingested_at=datetime.now(timezone.utc),
        pages=[Page(page_number=1, width=612, height=792, elements=elements)],
    )

    # Create matching PDF
    pdf = fitz.open()
    page = pdf.new_page(width=612, height=792)
    page.insert_text((50, 110), "Old Pressure: 45 barg", fontsize=10)
    page.insert_text((50, 140), "Equipment Tag: 26-KC-501", fontsize=10)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.save(tmp.name)
    pdf.close()
    tmp.close()

    return doc, tmp.name


class TestMarkupOverlay:
    """Tests for the PDF markup overlay."""

    def test_markup_adds_annotations(self):
        """Annotated PDF should have more annotations than the original."""
        doc, pdf_path = _make_doc_and_pdf()

        records = [
            DeltaRecord(
                change_id="test-mod-001", document_a="A", document_b="B",
                change_type="modified", element_type="text", page=1,
                old_value="Old Pressure: 45 barg", new_value="New Pressure: 48 barg",
                description="Pressure changed", confidence=0.95,
                bbox_a=(50.0, 100.0, 250.0, 115.0), bbox_b=(50.0, 100.0, 250.0, 115.0),
            ),
            DeltaRecord(
                change_id="test-rem-001", document_a="A", document_b="B",
                change_type="removed", element_type="text", page=1,
                old_value="Equipment Tag: 26-KC-501", new_value=None,
                description="Tag removed", confidence=1.0,
                bbox_a=(50.0, 130.0, 280.0, 145.0), bbox_b=None,
            ),
        ]

        try:
            # Count annotations in original
            orig = fitz.open(pdf_path)
            orig_annots = sum(len(list(page.annots() or [])) for page in orig)
            orig.close()

            # Generate markup
            annotated_bytes = render_markup(doc, records, pdf_path, side="a")

            # Count annotations in annotated
            annotated = fitz.open(stream=annotated_bytes, filetype="pdf")
            new_annots = sum(len(list(page.annots() or [])) for page in annotated)
            annotated.close()

            assert new_annots > orig_annots, (
                f"Expected more annotations after markup. Original: {orig_annots}, Annotated: {new_annots}"
            )
            assert new_annots >= 2  # At least our 2 records
        finally:
            os.unlink(pdf_path)

    def test_markup_dwg_raises_error(self):
        """DWG format should raise a clear ValueError."""
        doc = CanonicalDocument(
            document_id="DWG-TEST", revision="A", format="dwg",
            source_filename="test.dwg", ingested_at=datetime.now(timezone.utc),
            pages=[], metadata={},
        )

        with pytest.raises(ValueError, match="DWG markup overlay is not supported"):
            render_markup(doc, [], "/fake/path.dwg", side="a")
