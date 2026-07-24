"""End-to-end evaluation test — runs the real eval pipeline against Phase 8 data.

This is NOT mocked. It ingests real synthetic PDFs and verifies sane P/R/F1.
Requires tesseract to be installed (for pair_003 OCR path).

Run: pytest backend/tests/test_eval_e2e.py -v
"""

import json
import os
import sys
from pathlib import Path

import pytest

os.environ["TESTING"] = "true"

from src.ingest.registry import registry
from src.delta.engine import compare_documents
from eval.metrics import score_delta


SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
DATASETS_DIR = Path(__file__).resolve().parent.parent / "eval" / "datasets"


def _ensure_pairs_exist():
    """Generate synthetic pairs if not already present."""
    if not (SAMPLES_DIR / "pair_001" / "base.pdf").exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from eval.generate_synthetic import main as gen
        gen()


class TestEvalEndToEnd:
    """Real end-to-end eval using the 3 synthetic pairs."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _ensure_pairs_exist()

    def _load_cases(self):
        with open(DATASETS_DIR / "delta_cases.json") as f:
            return json.load(f)

    def test_all_pairs_ingest_and_compare(self):
        """All 3 pairs can be ingested and compared without errors."""
        cases = self._load_cases()
        for case in cases:
            doc_a = registry.ingest_file(
                str(SAMPLES_DIR / case["doc_a_path"]),
                f"E2E-{case['pair_id']}-A", "A"
            )
            doc_b = registry.ingest_file(
                str(SAMPLES_DIR / case["doc_b_path"]),
                f"E2E-{case['pair_id']}-B", "B"
            )
            records = compare_documents(doc_a, doc_b)
            assert len(records) > 0, f"No changes detected for {case['pair_id']}"

    def test_pair_001_recall_is_1(self):
        """Pair 001 (native→native) should have perfect recall."""
        cases = self._load_cases()
        case = cases[0]
        assert case["pair_id"] == "pair_001"

        doc_a = registry.ingest_file(
            str(SAMPLES_DIR / case["doc_a_path"]), "E2E-P1A", "A"
        )
        doc_b = registry.ingest_file(
            str(SAMPLES_DIR / case["doc_b_path"]), "E2E-P1B", "B"
        )
        records = compare_documents(doc_a, doc_b)
        result = score_delta(case["expected_changes"], records)

        assert result["recall"] == 1.0, f"Missed changes: {result['missed']}"
        assert result["precision"] > 0.7  # Some FPs expected (Rev change)

    def test_pair_002_detects_shifted_line(self):
        """Pair 002 must detect the inserted NOTE 6 (shifted-line scenario)."""
        cases = self._load_cases()
        case = cases[1]
        assert case["pair_id"] == "pair_002"

        doc_a = registry.ingest_file(
            str(SAMPLES_DIR / case["doc_a_path"]), "E2E-P2A", "A"
        )
        doc_b = registry.ingest_file(
            str(SAMPLES_DIR / case["doc_b_path"]), "E2E-P2B", "B"
        )
        records = compare_documents(doc_a, doc_b)
        result = score_delta(case["expected_changes"], records)

        assert result["recall"] == 1.0
        # Verify the shifted-line note was detected as added
        added_values = [r.new_value for r in records if r.change_type == "added"]
        assert any("HIGH-HIGH LEVEL" in (v or "") for v in added_values)

    def test_pair_003_ocr_path_detects_key_changes(self):
        """Pair 003 (native→scanned) must detect the pump tag and flow changes."""
        cases = self._load_cases()
        case = cases[2]
        assert case["pair_id"] == "pair_003"

        doc_a = registry.ingest_file(
            str(SAMPLES_DIR / case["doc_a_path"]), "E2E-P3A", "A"
        )
        doc_b = registry.ingest_file(
            str(SAMPLES_DIR / case["doc_b_path"]), "E2E-P3B", "B"
        )

        # Verify OCR path was used
        assert doc_b.format == "scanned_pdf"

        records = compare_documents(doc_a, doc_b)
        result = score_delta(case["expected_changes"], records)

        # Recall should be 1.0 for the key changes
        assert result["recall"] == 1.0, f"Missed: {result['missed']}"
        # Precision will be low due to OCR noise — that's expected and honest
        assert result["precision"] < 0.5  # Confirm OCR noise is real

    def test_aggregate_f1_is_sane(self):
        """Aggregate F1 across all 3 pairs should be non-trivial (not 0, not 1.0)."""
        cases = self._load_cases()
        f1_scores = []

        for case in cases:
            doc_a = registry.ingest_file(
                str(SAMPLES_DIR / case["doc_a_path"]),
                f"E2E-AGG-{case['pair_id']}-A", "A"
            )
            doc_b = registry.ingest_file(
                str(SAMPLES_DIR / case["doc_b_path"]),
                f"E2E-AGG-{case['pair_id']}-B", "B"
            )
            records = compare_documents(doc_a, doc_b)
            result = score_delta(case["expected_changes"], records)
            f1_scores.append(result["f1"])

        avg_f1 = sum(f1_scores) / len(f1_scores)
        assert avg_f1 > 0.3, f"F1 too low: {avg_f1}"
        assert avg_f1 < 1.0, f"F1 suspiciously perfect: {avg_f1}"
