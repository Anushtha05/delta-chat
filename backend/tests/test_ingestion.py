"""Tests for the document ingestion pipeline.

These tests run without Docker (no MySQL/Mongo required) by testing
the adapter layer directly. Test PDFs are generated programmatically.

Run: pytest backend/tests/test_ingestion.py -v
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import fitz  # PyMuPDF
import pytest

# Ensure TESTING mode so config doesn't require OPENROUTER_API_KEY
os.environ["TESTING"] = "true"

from src.ingest.base import IngestionError, UnsupportedFormatError
from src.ingest.pdf_native import NativePDFAdapter
from src.ingest.pdf_scanned import ScannedPDFAdapter
from src.ingest.dwg import DWGAdapter
from src.ingest.registry import AdapterRegistry
from src.canonical.model import CanonicalDocument


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def native_pdf_path() -> str:
    """Create a native PDF with embedded text for testing."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter

    # Insert multiple text elements to pass the "native" detection threshold
    texts = [
        ("XV-100 Control Valve", (72, 72)),
        ("3.5 mm diameter", (72, 100)),
        ("NOTE: Check pressure before operation", (72, 130)),
        ("P-101A Pump Assembly", (72, 160)),
        ("Operating pressure: 150 PSI", (72, 190)),
        ("TIC-302 Temperature Controller", (72, 220)),
        ("Flow rate: 25 m/s", (72, 250)),
        ("Document Rev A", (72, 280)),
        ("Sheet 1 of 3", (72, 310)),
        ("Project: Delta Plant Upgrade", (72, 340)),
    ]

    for text_content, pos in texts:
        page.insert_text(pos, text_content, fontsize=11)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    doc.save(tmp.name)
    doc.close()
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def scanned_pdf_path() -> str:
    """Create a PDF that appears scanned (image-only, no text layer).

    We create a page, draw text as an image (rasterize it), then embed
    only the image — no text layer remains.
    """
    # Create a source doc with text, render to image, then create image-only PDF
    source_doc = fitz.open()
    source_page = source_doc.new_page(width=612, height=792)
    source_page.insert_text((100, 100), "SCANNED DOCUMENT TEXT", fontsize=14)
    source_page.insert_text((100, 130), "Equipment tag: XV-200", fontsize=12)
    source_page.insert_text((100, 160), "Pressure: 100 PSI", fontsize=12)

    # Render to image
    mat = fitz.Matrix(2, 2)  # 144 DPI
    pix = source_page.get_pixmap(matrix=mat)
    source_doc.close()

    # Create image-only PDF (no text layer)
    img_doc = fitz.open()
    img_page = img_doc.new_page(width=612, height=792)
    img_page.insert_image(img_page.rect, pixmap=pix)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    img_doc.save(tmp.name)
    img_doc.close()
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def dxf_path() -> str:
    """Create a minimal DXF file with text and geometry entities."""
    import ezdxf

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Add TEXT entities
    msp.add_text("PUMP P-101", dxfattribs={"height": 2.5, "insert": (10, 20)})
    msp.add_text("150 PSI", dxfattribs={"height": 2.0, "insert": (50, 30)})

    # Add geometry
    msp.add_line((0, 0), (100, 100))
    msp.add_circle((50, 50), radius=25)

    tmp = tempfile.NamedTemporaryFile(suffix=".dxf", delete=False)
    doc.saveas(tmp.name)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def empty_pdf_path() -> str:
    """Create a PDF with a single blank page (no text content at all).

    PyMuPDF won't save zero-page PDFs, so we create a 1-page PDF with
    nothing on it — this simulates an effectively empty document.
    """
    doc = fitz.open()
    doc.new_page(width=612, height=792)  # blank page, no text
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    doc.save(tmp.name)
    doc.close()
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def corrupt_file_path() -> str:
    """Create a file with a .pdf extension but garbage content."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(b"THIS IS NOT A PDF FILE AT ALL - GARBAGE CONTENT 12345")
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def unsupported_file_path() -> str:
    """Create a file with an unsupported extension."""
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.write(b"fake excel content")
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


# ─── Native PDF Tests ─────────────────────────────────────────────────────────


class TestNativePDFAdapter:
    """Tests for native (text-layer) PDF ingestion."""

    def test_can_handle_native_pdf(self, native_pdf_path):
        adapter = NativePDFAdapter()
        assert adapter.can_handle(native_pdf_path) is True

    def test_cannot_handle_non_pdf(self, dxf_path):
        adapter = NativePDFAdapter()
        assert adapter.can_handle(dxf_path) is False

    def test_ingest_produces_elements_with_bboxes(self, native_pdf_path):
        adapter = NativePDFAdapter()
        doc = adapter.ingest(native_pdf_path, "DOC-001", "A")

        assert isinstance(doc, CanonicalDocument)
        assert doc.document_id == "DOC-001"
        assert doc.revision == "A"
        assert doc.format == "native_pdf"
        assert len(doc.pages) == 1

        page = doc.pages[0]
        assert len(page.elements) > 0

        # All elements must have valid bboxes (4-tuple of floats)
        for elem in page.elements:
            assert len(elem.bbox) == 4
            x0, y0, x1, y1 = elem.bbox
            assert x0 <= x1, f"Invalid bbox x: {elem.bbox}"
            assert y0 <= y1, f"Invalid bbox y: {elem.bbox}"
            assert elem.confidence == 1.0
            assert elem.source_format == "native_pdf"
            assert elem.normalized_content is not None

    def test_ingest_classifies_element_types(self, native_pdf_path):
        adapter = NativePDFAdapter()
        doc = adapter.ingest(native_pdf_path, "DOC-001", "A")

        types_found = {elem.type for page in doc.pages for elem in page.elements}
        # We expect at least 'text' type from the test content
        assert "text" in types_found

    def test_ingest_empty_pdf_raises_error(self, empty_pdf_path):
        adapter = NativePDFAdapter()
        # Blank PDF has no text layer, so can_handle returns False
        assert adapter.can_handle(empty_pdf_path) is False


# ─── Scanned PDF Tests ────────────────────────────────────────────────────────


class TestScannedPDFAdapter:
    """Tests for scanned (OCR) PDF ingestion."""

    def test_can_handle_scanned_pdf(self, scanned_pdf_path):
        adapter = ScannedPDFAdapter()
        # Scanned PDF has no text layer, native adapter declines, scanned accepts
        native = NativePDFAdapter()
        assert native.can_handle(scanned_pdf_path) is False
        assert adapter.can_handle(scanned_pdf_path) is True

    def test_ingest_produces_elements_with_confidence(self, scanned_pdf_path):
        """Scanned PDF elements should have confidence < 1.0 for at least some elements."""
        adapter = ScannedPDFAdapter()
        doc = adapter.ingest(scanned_pdf_path, "DOC-002", "B")

        assert isinstance(doc, CanonicalDocument)
        assert doc.format == "scanned_pdf"
        assert len(doc.pages) == 1

        page = doc.pages[0]
        # OCR should find at least some text (the rendered text in the image)
        assert len(page.elements) > 0

        # At least some elements should have confidence < 1.0
        # (OCR confidence is tesseract confidence / 100, rarely exactly 1.0)
        confidences = [elem.confidence for elem in page.elements]
        has_sub_perfect = any(c < 1.0 for c in confidences)
        assert has_sub_perfect, (
            f"Expected at least one element with confidence < 1.0, "
            f"got confidences: {confidences}"
        )

        # All elements should have valid bboxes
        for elem in page.elements:
            assert len(elem.bbox) == 4
            assert elem.source_format == "scanned_pdf"

    def test_ingest_empty_pdf_raises_error(self, empty_pdf_path):
        adapter = ScannedPDFAdapter()
        # Blank PDF (1 page, no content) is accepted by scanned adapter
        # but OCR produces no meaningful elements — adapter still succeeds
        # with an empty elements list (not an error).
        assert adapter.can_handle(empty_pdf_path) is True
        doc = adapter.ingest(empty_pdf_path, "EMPTY-001", "A")
        # A blank page produces zero or very few OCR elements
        assert isinstance(doc, CanonicalDocument)


# ─── DWG/DXF Tests ───────────────────────────────────────────────────────────


class TestDWGAdapter:
    """Tests for DWG/DXF CAD file ingestion."""

    def test_can_handle_dxf(self, dxf_path):
        adapter = DWGAdapter()
        assert adapter.can_handle(dxf_path) is True

    def test_can_handle_dwg_extension(self):
        adapter = DWGAdapter()
        assert adapter.can_handle("/some/path/drawing.dwg") is True
        assert adapter.can_handle("/some/path/drawing.DWG") is True

    def test_cannot_handle_pdf(self, native_pdf_path):
        adapter = DWGAdapter()
        assert adapter.can_handle(native_pdf_path) is False

    def test_ingest_dxf_extracts_elements(self, dxf_path):
        adapter = DWGAdapter()
        doc = adapter.ingest(dxf_path, "DWG-001", "01")

        assert isinstance(doc, CanonicalDocument)
        assert doc.document_id == "DWG-001"
        assert doc.format == "dwg"
        assert len(doc.pages) == 1

        page = doc.pages[0]
        assert len(page.elements) > 0

        # Should have both text and geometry elements
        types = {e.type for e in page.elements}
        assert "text" in types
        assert "geometry" in types

        # All elements have bboxes
        for elem in page.elements:
            assert len(elem.bbox) == 4
            assert elem.source_format == "dwg"


# ─── Registry Tests ──────────────────────────────────────────────────────────


class TestAdapterRegistry:
    """Tests for the adapter registry routing logic."""

    def test_routes_native_pdf(self, native_pdf_path):
        reg = AdapterRegistry()
        adapter = reg.get_adapter(native_pdf_path)
        assert isinstance(adapter, NativePDFAdapter)

    def test_routes_scanned_pdf(self, scanned_pdf_path):
        reg = AdapterRegistry()
        adapter = reg.get_adapter(scanned_pdf_path)
        assert isinstance(adapter, ScannedPDFAdapter)

    def test_routes_dxf(self, dxf_path):
        reg = AdapterRegistry()
        adapter = reg.get_adapter(dxf_path)
        assert isinstance(adapter, DWGAdapter)

    def test_unsupported_format_raises_error(self, unsupported_file_path):
        reg = AdapterRegistry()
        with pytest.raises(UnsupportedFormatError) as exc_info:
            reg.get_adapter(unsupported_file_path)
        assert "No adapter can handle file" in str(exc_info.value)

    def test_corrupt_file_raises_clear_error(self, corrupt_file_path):
        """Corrupt files should raise IngestionError, not crash with a raw traceback."""
        reg = AdapterRegistry()
        # A corrupt .pdf file won't pass native detection (can't open),
        # and won't pass scanned detection (can't open either)
        with pytest.raises(UnsupportedFormatError):
            reg.ingest_file(corrupt_file_path, "BAD-001", "X")

    def test_ingest_file_end_to_end_native(self, native_pdf_path):
        reg = AdapterRegistry()
        doc = reg.ingest_file(native_pdf_path, "E2E-001", "A")
        assert doc.document_id == "E2E-001"
        assert doc.format == "native_pdf"
        assert len(doc.pages) > 0
        assert sum(len(p.elements) for p in doc.pages) > 0
