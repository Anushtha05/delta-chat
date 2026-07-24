"""Tests for delta report generation, persistence, and chunking.

These tests run without Docker — they test report generation and chunking logic
using synthetic data. File-writing tests use temp directories.

Run: pytest backend/tests/test_report.py -v
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["TESTING"] = "true"

from src.canonical.model import CanonicalDocument, Element, Page
from src.delta.model import DeltaRecord
from src.delta.engine import compare_documents
from src.delta.report import generate_json_report, generate_markdown_report
from src.delta.persist import write_report_files
from src.chat.chunker import chunk_document, chunk_delta_records


# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_element(content: str, page: int = 1, elem_type: str = "text",
                  bbox: tuple = (10.0, 10.0, 100.0, 20.0)) -> Element:
    """Helper to create a test Element."""
    from src.delta.normalize import normalize
    return Element(
        id=str(uuid.uuid4()),
        type=elem_type,
        content=content,
        normalized_content=normalize(content),
        bbox=bbox,
        page_number=page,
        confidence=1.0,
        source_format="native_pdf",
    )


@pytest.fixture
def doc_a() -> CanonicalDocument:
    """Create a test document A (base revision)."""
    elements = [
        _make_element("XV-100 Control Valve", page=1, elem_type="equipment"),
        _make_element("Operating Pressure: 150 PSI", page=1, elem_type="technical_value"),
        _make_element("TIC-302 Temperature Controller", page=1, elem_type="instrument"),
        _make_element("Flow Rate: 3.5 m/s", page=1, elem_type="technical_value"),
        _make_element("NOTE: Check valve before startup", page=1, elem_type="note"),
        _make_element("Page 2 content here", page=2, elem_type="text", bbox=(10, 10, 200, 30)),
        _make_element("P-101A Main Pump", page=2, elem_type="equipment", bbox=(10, 40, 150, 55)),
    ]
    return CanonicalDocument(
        document_id="DOC-A",
        revision="1",
        format="native_pdf",
        source_filename="doc_a.pdf",
        ingested_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        pages=[
            Page(page_number=1, width=612, height=792,
                 elements=[e for e in elements if e.page_number == 1]),
            Page(page_number=2, width=612, height=792,
                 elements=[e for e in elements if e.page_number == 2]),
        ],
    )


@pytest.fixture
def doc_b() -> CanonicalDocument:
    """Create a test document B (newer revision with some changes)."""
    elements = [
        # Same as doc_a
        _make_element("XV-100 Control Valve", page=1, elem_type="equipment"),
        # Modified: pressure changed
        _make_element("Operating Pressure: 200 PSI", page=1, elem_type="technical_value"),
        # Same
        _make_element("TIC-302 Temperature Controller", page=1, elem_type="instrument"),
        # Removed: "Flow Rate: 3.5 m/s" is gone
        # Modified note
        _make_element("NOTE: Check valve and pressure before startup", page=1, elem_type="note"),
        # Added new element
        _make_element("FIC-401 Flow Controller", page=1, elem_type="instrument"),
        # Page 2: same content
        _make_element("Page 2 content here", page=2, elem_type="text", bbox=(10, 10, 200, 30)),
        # Modified pump tag
        _make_element("P-101B Main Pump (upgraded)", page=2, elem_type="equipment", bbox=(10, 40, 150, 55)),
    ]
    return CanonicalDocument(
        document_id="DOC-B",
        revision="2",
        format="native_pdf",
        source_filename="doc_b.pdf",
        ingested_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        pages=[
            Page(page_number=1, width=612, height=792,
                 elements=[e for e in elements if e.page_number == 1]),
            Page(page_number=2, width=612, height=792,
                 elements=[e for e in elements if e.page_number == 2]),
        ],
    )


@pytest.fixture
def delta_records(doc_a, doc_b) -> list[DeltaRecord]:
    """Produce delta records from comparing doc_a and doc_b."""
    return compare_documents(doc_a, doc_b)


@pytest.fixture
def json_report(delta_records, doc_a, doc_b) -> dict:
    """Generate a JSON report from delta records."""
    doc_a_meta = {
        "document_id": doc_a.document_id,
        "revision": doc_a.revision,
        "format": doc_a.format,
        "source_filename": doc_a.source_filename,
    }
    doc_b_meta = {
        "document_id": doc_b.document_id,
        "revision": doc_b.revision,
        "format": doc_b.format,
        "source_filename": doc_b.source_filename,
    }
    return generate_json_report(delta_records, doc_a_meta, doc_b_meta)


# ─── Delta Engine Tests ───────────────────────────────────────────────────────


class TestDeltaEngine:
    """Tests for the comparison engine."""

    def test_produces_records(self, delta_records):
        """Engine should detect changes between the two documents."""
        assert len(delta_records) > 0

    def test_detects_all_change_types(self, delta_records):
        """Engine should detect added, removed, and modified elements."""
        types = {r.change_type for r in delta_records}
        assert "added" in types
        assert "removed" in types
        assert "modified" in types

    def test_modified_has_old_and_new(self, delta_records):
        """Modified records must have both old_value and new_value."""
        modified = [r for r in delta_records if r.change_type == "modified"]
        assert len(modified) > 0
        for r in modified:
            assert r.old_value is not None
            assert r.new_value is not None
            assert r.old_value != r.new_value

    def test_added_has_only_new_value(self, delta_records):
        """Added records must have new_value but not old_value."""
        added = [r for r in delta_records if r.change_type == "added"]
        assert len(added) > 0
        for r in added:
            assert r.new_value is not None
            assert r.old_value is None

    def test_removed_has_only_old_value(self, delta_records):
        """Removed records must have old_value but not new_value."""
        removed = [r for r in delta_records if r.change_type == "removed"]
        assert len(removed) > 0
        for r in removed:
            assert r.old_value is not None
            assert r.new_value is None


# ─── JSON Report Tests ────────────────────────────────────────────────────────


class TestJsonReport:
    """Tests for JSON report generation."""

    def test_report_structure(self, json_report):
        """JSON report must have required top-level keys."""
        assert "document_a" in json_report
        assert "document_b" in json_report
        assert "generated_at" in json_report
        assert "summary" in json_report
        assert "changes" in json_report

    def test_summary_counts_match_changes(self, json_report):
        """Summary counts must match actual changes list grouped by type."""
        summary = json_report["summary"]
        changes = json_report["changes"]

        added_count = len([c for c in changes if c["change_type"] == "added"])
        removed_count = len([c for c in changes if c["change_type"] == "removed"])
        modified_count = len([c for c in changes if c["change_type"] == "modified"])

        assert summary["added"] == added_count
        assert summary["removed"] == removed_count
        assert summary["modified"] == modified_count

    def test_total_changes_equals_sum(self, json_report):
        """Total changes should equal sum of all types."""
        summary = json_report["summary"]
        total = summary["added"] + summary["removed"] + summary["modified"]
        assert total == len(json_report["changes"])

    def test_document_metadata_present(self, json_report):
        """Both document metadata dicts should have document_id."""
        assert json_report["document_a"]["document_id"] == "DOC-A"
        assert json_report["document_b"]["document_id"] == "DOC-B"

    def test_changes_have_required_fields(self, json_report):
        """Each change entry must have all required fields."""
        required_fields = {"change_id", "change_type", "element_type", "page",
                          "old_value", "new_value", "description", "confidence"}
        for change in json_report["changes"]:
            assert required_fields.issubset(change.keys()), (
                f"Missing fields: {required_fields - change.keys()}"
            )


# ─── Markdown Report Tests ────────────────────────────────────────────────────


class TestMarkdownReport:
    """Tests for Markdown report generation."""

    def test_markdown_is_string(self, json_report):
        md = generate_markdown_report(json_report)
        assert isinstance(md, str)
        assert len(md) > 100  # should be substantial

    def test_markdown_has_title(self, json_report):
        md = generate_markdown_report(json_report)
        assert "# Delta Report:" in md
        assert "DOC-A" in md
        assert "DOC-B" in md

    def test_markdown_has_summary_table(self, json_report):
        md = generate_markdown_report(json_report)
        assert "## Summary" in md
        assert "| Change Type | Count |" in md
        assert "Added" in md
        assert "Removed" in md
        assert "Modified" in md

    def test_markdown_has_change_sections(self, json_report):
        md = generate_markdown_report(json_report)
        # Should have at least one section for changes
        assert "###" in md  # individual change headers

    def test_markdown_shows_old_new_values(self, json_report):
        md = generate_markdown_report(json_report)
        assert "Old value:" in md or "Value:" in md
        assert "New value:" in md or "Value:" in md


# ─── File Output Tests ────────────────────────────────────────────────────────


class TestReportFileOutput:
    """Tests for writing report files to disk."""

    def test_files_written_to_outputs(self, json_report):
        """Report files must be written to outputs/reports/ directory."""
        md = generate_markdown_report(json_report)

        # Use a temp directory to avoid polluting the real outputs
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.delta.persist._OUTPUTS_DIR", Path(tmpdir)):
                paths = write_report_files(json_report, md, "DOC-A", "DOC-B")

            json_path = Path(paths["json_path"])
            md_path = Path(paths["md_path"])

            assert json_path.exists()
            assert md_path.exists()

            # Verify JSON is valid
            with open(json_path) as f:
                loaded = json.load(f)
            assert loaded["summary"]["added"] == json_report["summary"]["added"]

            # Verify Markdown content
            md_content = md_path.read_text()
            assert "# Delta Report:" in md_content

    def test_filenames_correct(self, json_report):
        """Filenames should follow the {doc_a}_vs_{doc_b} pattern."""
        md = generate_markdown_report(json_report)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.delta.persist._OUTPUTS_DIR", Path(tmpdir)):
                paths = write_report_files(json_report, md, "DOC-A", "DOC-B")

            assert "DOC-A_vs_DOC-B.json" in paths["json_path"]
            assert "DOC-A_vs_DOC-B.md" in paths["md_path"]


# ─── Chunker Tests ────────────────────────────────────────────────────────────


class TestChunker:
    """Tests for the document/delta chunker."""

    def test_chunk_document_produces_one_per_page(self, doc_a):
        """Should produce at least 1 chunk per page with elements."""
        chunks = chunk_document(doc_a, "PID_A")
        # doc_a has 2 pages with elements
        assert len(chunks) >= 2

        pages_seen = {c["page"] for c in chunks}
        assert 1 in pages_seen
        assert 2 in pages_seen

    def test_chunk_document_fields(self, doc_a):
        """Each chunk must have required fields."""
        chunks = chunk_document(doc_a, "PID_A")
        required = {"chunk_id", "source", "document_id", "page", "text", "bbox_union", "delta_change_id"}
        for chunk in chunks:
            assert required.issubset(chunk.keys())
            assert chunk["source"] == "PID_A"
            assert chunk["document_id"] == "DOC-A"
            assert chunk["delta_change_id"] is None
            assert len(chunk["text"]) > 0
            assert len(chunk["bbox_union"]) == 4

    def test_chunk_delta_records_one_per_record(self, delta_records):
        """Should produce exactly one chunk per DeltaRecord."""
        chunks = chunk_delta_records(delta_records, "DOC-A", "DOC-B")
        assert len(chunks) == len(delta_records)

    def test_chunk_delta_records_fields(self, delta_records):
        """Each delta chunk must have required fields and source=DELTA_REPORT."""
        chunks = chunk_delta_records(delta_records, "DOC-A", "DOC-B")
        for chunk in chunks:
            assert chunk["source"] == "DELTA_REPORT"
            assert chunk["document_id"] == "DOC-A_vs_DOC-B"
            assert chunk["delta_change_id"] is not None
            assert len(chunk["text"]) > 0

    def test_chunk_delta_records_change_id_matches(self, delta_records):
        """Each delta chunk's delta_change_id should correspond to a real record."""
        chunks = chunk_delta_records(delta_records, "DOC-A", "DOC-B")
        record_ids = {r.change_id for r in delta_records}
        for chunk in chunks:
            assert chunk["delta_change_id"] in record_ids
