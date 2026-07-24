"""Tests for the canonical document model — structural validation.

Verifies that ingested documents have proper page_number, text content,
bounding boxes, and metadata fields.
"""

import os
import tempfile

import fitz
import pytest

os.environ["TESTING"] = "true"

from src.canonical.model import CanonicalDocument, Element, Page
from src.ingest.registry import registry


@pytest.fixture
def ingested_doc():
    """Ingest a real synthetic PDF and return the CanonicalDocument."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "Equipment Tag: 26-KC-501", fontsize=11)
    page.insert_text((72, 130), "Design Pressure: 120 barg", fontsize=10)
    page.insert_text((72, 160), "Flow Rate: 15.2 MMSCFD", fontsize=10)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    doc.save(tmp.name)
    doc.close()
    tmp.close()

    try:
        result = registry.ingest_file(tmp.name, "MODEL-TEST-001", "A")
        yield result
    finally:
        os.unlink(tmp.name)


class TestCanonicalModel:
    """Validate canonical document model fields after ingestion."""

    def test_document_has_pages(self, ingested_doc):
        assert len(ingested_doc.pages) >= 1

    def test_page_has_page_number(self, ingested_doc):
        for page in ingested_doc.pages:
            assert page.page_number >= 1

    def test_page_has_dimensions(self, ingested_doc):
        page = ingested_doc.pages[0]
        assert page.width > 0
        assert page.height > 0

    def test_elements_have_text_content(self, ingested_doc):
        page = ingested_doc.pages[0]
        assert len(page.elements) > 0
        for elem in page.elements:
            assert isinstance(elem.content, str)
            assert len(elem.content.strip()) > 0

    def test_elements_have_valid_bbox(self, ingested_doc):
        for page in ingested_doc.pages:
            for elem in page.elements:
                assert len(elem.bbox) == 4
                x0, y0, x1, y1 = elem.bbox
                assert isinstance(x0, float)
                assert isinstance(y0, float)
                assert x0 <= x1
                assert y0 <= y1

    def test_elements_have_page_number(self, ingested_doc):
        for page in ingested_doc.pages:
            for elem in page.elements:
                assert elem.page_number == page.page_number

    def test_document_has_metadata_fields(self, ingested_doc):
        assert ingested_doc.document_id == "MODEL-TEST-001"
        assert ingested_doc.revision == "A"
        assert ingested_doc.format in ("native_pdf", "scanned_pdf", "dwg")
        assert ingested_doc.source_filename is not None
        assert ingested_doc.ingested_at is not None

    def test_elements_have_normalized_content(self, ingested_doc):
        for page in ingested_doc.pages:
            for elem in page.elements:
                assert elem.normalized_content is not None
                # Normalized should be lowercase
                assert elem.normalized_content == elem.normalized_content.lower()
