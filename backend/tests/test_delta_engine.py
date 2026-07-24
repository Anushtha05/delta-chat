"""Tests for delta engine edge cases — determinism, numeric detection, alignment.

Covers gaps not addressed in test_report.py:
- Numeric change detection (value changes in technical fields)
- Location (bbox) present on all records
- Confidence present on all records
- Determinism: repeated runs produce identical output
- Alignment regression: shifted lines don't produce false modifications
"""

import os
import uuid
from datetime import datetime, timezone

import pytest

os.environ["TESTING"] = "true"

from src.canonical.model import CanonicalDocument, Element, Page
from src.delta.engine import compare_documents
from src.delta.normalize import normalize


def _el(content, page=1, bbox=(10.0, 10.0, 100.0, 20.0), etype="text"):
    return Element(
        id=str(uuid.uuid4()),
        type=etype,
        content=content,
        normalized_content=normalize(content),
        bbox=bbox,
        page_number=page,
        confidence=1.0,
        source_format="native_pdf",
    )


def _doc(doc_id, elements):
    pages_map = {}
    for e in elements:
        pages_map.setdefault(e.page_number, []).append(e)
    pages = [
        Page(page_number=pn, width=612, height=792, elements=elems)
        for pn, elems in sorted(pages_map.items())
    ]
    return CanonicalDocument(
        document_id=doc_id, revision="1", format="native_pdf",
        source_filename=f"{doc_id}.pdf", ingested_at=datetime.now(timezone.utc),
        pages=pages,
    )


class TestNumericChangeDetection:
    """The engine must detect changes in numeric/technical values."""

    def test_detects_numeric_value_change(self):
        """A change from '776 kW' to '800 kW' must be detected as modified."""
        doc_a = _doc("A", [_el("Duty: 776 kW")])
        doc_b = _doc("B", [_el("Duty: 800 kW")])
        records = compare_documents(doc_a, doc_b)

        modified = [r for r in records if r.change_type == "modified"]
        assert len(modified) == 1
        assert "776" in modified[0].old_value
        assert "800" in modified[0].new_value

    def test_detects_pressure_change(self):
        """Pressure value change should be detected."""
        doc_a = _doc("A", [_el("Suction Pressure: 45.2 barg")])
        doc_b = _doc("B", [_el("Suction Pressure: 48.0 barg")])
        records = compare_documents(doc_a, doc_b)

        modified = [r for r in records if r.change_type == "modified"]
        assert len(modified) == 1
        assert "45.2" in modified[0].old_value
        assert "48.0" in modified[0].new_value

    def test_identical_numeric_not_flagged(self):
        """Identical values should not produce any changes."""
        doc_a = _doc("A", [_el("Duty: 776 kW")])
        doc_b = _doc("B", [_el("Duty: 776 kW")])
        records = compare_documents(doc_a, doc_b)
        assert len(records) == 0


class TestLocationAndConfidence:
    """All delta records must carry location (bbox) and confidence."""

    def test_modified_has_bbox_a_and_b(self):
        doc_a = _doc("A", [_el("Tag: 26-KA-901", bbox=(50, 100, 200, 115))])
        doc_b = _doc("B", [_el("Tag: 26-KA-901A", bbox=(50, 100, 210, 115))])
        records = compare_documents(doc_a, doc_b)

        assert len(records) == 1
        r = records[0]
        assert r.bbox_a is not None
        assert r.bbox_b is not None
        assert len(r.bbox_a) == 4
        assert len(r.bbox_b) == 4

    def test_added_has_bbox_b(self):
        doc_a = _doc("A", [_el("Existing line")])
        doc_b = _doc("B", [_el("Existing line"), _el("New line", bbox=(10, 50, 200, 65))])
        records = compare_documents(doc_a, doc_b)

        added = [r for r in records if r.change_type == "added"]
        assert len(added) == 1
        assert added[0].bbox_b is not None
        assert added[0].bbox_a is None

    def test_removed_has_bbox_a(self):
        doc_a = _doc("A", [_el("Will be removed", bbox=(10, 50, 200, 65)), _el("Stays")])
        doc_b = _doc("B", [_el("Stays")])
        records = compare_documents(doc_a, doc_b)

        removed = [r for r in records if r.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].bbox_a is not None
        assert removed[0].bbox_b is None

    def test_all_records_have_confidence(self):
        doc_a = _doc("A", [_el("Old value"), _el("Removed")])
        doc_b = _doc("B", [_el("New value"), _el("Added")])
        records = compare_documents(doc_a, doc_b)

        for r in records:
            assert r.confidence is not None
            assert 0.0 <= r.confidence <= 1.0


class TestDeterminism:
    """Repeated runs on identical input must produce identical output."""

    def test_repeat_run_same_results(self):
        """Running compare_documents twice with the same input yields same changes."""
        elements_a = [_el("Line 1"), _el("Line 2"), _el("Line 3")]
        elements_b = [_el("Line 1"), _el("Line 2 modified"), _el("Line 4")]

        doc_a = _doc("A", elements_a)
        doc_b = _doc("B", elements_b)

        run1 = compare_documents(doc_a, doc_b)
        run2 = compare_documents(doc_a, doc_b)

        # Same count
        assert len(run1) == len(run2)

        # Same types in same order
        for r1, r2 in zip(run1, run2):
            assert r1.change_type == r2.change_type
            assert r1.old_value == r2.old_value
            assert r1.new_value == r2.new_value
            assert r1.page == r2.page


class TestAlignmentRegression:
    """Shifted lines (inserted content) should not cause false modifications."""

    def test_inserted_line_does_not_corrupt_existing(self):
        """Inserting a new line between existing lines should produce exactly 1 'added',
        not modify the surrounding lines."""
        doc_a = _doc("A", [
            _el("NOTE 1: First note", bbox=(50, 100, 400, 115)),
            _el("NOTE 2: Second note", bbox=(50, 120, 400, 135)),
            _el("NOTE 3: Third note", bbox=(50, 140, 400, 155)),
        ])
        doc_b = _doc("B", [
            _el("NOTE 1: First note", bbox=(50, 100, 400, 115)),
            _el("NOTE 2: Second note", bbox=(50, 120, 400, 135)),
            _el("NOTE 2A: Inserted note", bbox=(50, 140, 400, 155)),  # NEW
            _el("NOTE 3: Third note", bbox=(50, 160, 400, 175)),  # shifted down
        ])

        records = compare_documents(doc_a, doc_b)

        # Should detect exactly 1 addition
        added = [r for r in records if r.change_type == "added"]
        modified = [r for r in records if r.change_type == "modified"]
        removed = [r for r in records if r.change_type == "removed"]

        assert len(added) == 1
        assert "NOTE 2A" in added[0].new_value
        # NOTE 1, 2, 3 should NOT be modified or removed
        assert len(modified) == 0
        assert len(removed) == 0

    def test_removed_line_does_not_corrupt_remaining(self):
        """Removing a line from the middle should not modify surrounding lines."""
        doc_a = _doc("A", [
            _el("Line A"),
            _el("Line B - will be removed"),
            _el("Line C"),
        ])
        doc_b = _doc("B", [
            _el("Line A"),
            _el("Line C"),
        ])

        records = compare_documents(doc_a, doc_b)

        removed = [r for r in records if r.change_type == "removed"]
        modified = [r for r in records if r.change_type == "modified"]

        assert len(removed) == 1
        assert "Line B" in removed[0].old_value
        assert len(modified) == 0
