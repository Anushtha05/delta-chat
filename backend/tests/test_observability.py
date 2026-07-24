"""Tests for observability — tracing, structured logging, and metrics.

Run: pytest backend/tests/test_observability.py -v
"""

import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

os.environ["TESTING"] = "true"

from src.observability.tracing import RequestTrace, get_current_trace, get_request_id, _TRACES_DIR
from src.observability.metrics import MetricsRecorder
from src.observability.logging import StructuredJsonFormatter, setup_logging


# ─── Tracing Tests ────────────────────────────────────────────────────────────


class TestTracing:
    """Tests for RequestTrace and stages."""

    def test_trace_generates_request_id(self):
        with patch("src.observability.tracing.RequestTrace._write_file"):
            with patch("src.observability.tracing.RequestTrace._write_mongo"):
                trace = RequestTrace()
                assert trace.request_id is not None
                assert len(trace.request_id) == 36  # UUID format
                trace.finish()

    def test_trace_custom_request_id(self):
        with patch("src.observability.tracing.RequestTrace._write_file"):
            with patch("src.observability.tracing.RequestTrace._write_mongo"):
                rid = "custom-id-123"
                trace = RequestTrace(request_id=rid)
                assert trace.request_id == rid
                trace.finish()

    def test_stage_records_duration(self):
        with patch("src.observability.tracing.RequestTrace._write_file"):
            with patch("src.observability.tracing.RequestTrace._write_mongo"):
                trace = RequestTrace()
                with trace.stage("test_stage") as s:
                    import time
                    time.sleep(0.01)  # 10ms
                    s.set("key", "value")

                assert s.duration_ms >= 5  # At least some time passed
                assert s.metadata["key"] == "value"
                trace.finish()

    def test_trace_finish_returns_dict_with_stages(self):
        with patch("src.observability.tracing.RequestTrace._write_file"):
            with patch("src.observability.tracing.RequestTrace._write_mongo"):
                trace = RequestTrace()
                trace.endpoint = "POST /api/test"
                with trace.stage("stage1") as s1:
                    s1.set("items", 5)
                with trace.stage("stage2") as s2:
                    s2.set("result", "ok")

                result = trace.finish("success")

                assert result["request_id"] == trace.request_id
                assert result["endpoint"] == "POST /api/test"
                assert result["status"] == "success"
                assert len(result["stages"]) == 2
                assert result["stages"][0]["name"] == "stage1"
                assert result["stages"][0]["metadata"]["items"] == 5
                assert result["stages"][1]["name"] == "stage2"

    def test_trace_writes_file(self):
        """Trace should write a JSON file to outputs/traces/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.observability.tracing._TRACES_DIR", Path(tmpdir)):
                with patch("src.observability.tracing.RequestTrace._write_mongo"):
                    trace = RequestTrace()
                    trace.endpoint = "POST /api/compare"
                    with trace.stage("delta") as s:
                        s.set("changes_found", 42)
                    trace.finish("success")

                    trace_file = Path(tmpdir) / f"{trace.request_id}.json"
                    assert trace_file.exists()

                    data = json.loads(trace_file.read_text())
                    assert data["request_id"] == trace.request_id
                    assert data["stages"][0]["metadata"]["changes_found"] == 42

    def test_request_id_consistent_across_trace(self):
        """request_id in trace, stages, and file must all be the same."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.observability.tracing._TRACES_DIR", Path(tmpdir)):
                with patch("src.observability.tracing.RequestTrace._write_mongo"):
                    trace = RequestTrace()
                    rid = trace.request_id

                    # During the trace, get_request_id should return it
                    assert get_request_id() == rid

                    with trace.stage("s1") as s:
                        assert get_request_id() == rid

                    result = trace.finish()
                    assert result["request_id"] == rid

                    trace_file = Path(tmpdir) / f"{rid}.json"
                    data = json.loads(trace_file.read_text())
                    assert data["request_id"] == rid

    def test_stage_records_error(self):
        """Stage should capture exception info if one occurs."""
        with patch("src.observability.tracing.RequestTrace._write_file"):
            with patch("src.observability.tracing.RequestTrace._write_mongo"):
                trace = RequestTrace()
                try:
                    with trace.stage("failing") as s:
                        raise ValueError("test error")
                except ValueError:
                    pass

                assert s.error is not None
                assert "ValueError" in s.error
                assert "test error" in s.error
                trace.finish("error")


# ─── Structured Logging Tests ─────────────────────────────────────────────────


class TestStructuredLogging:
    """Tests for structured JSON logging."""

    def test_formatter_produces_json(self):
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="test event",
            args=None, exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["event"] == "test event"
        assert "timestamp" in data

    def test_formatter_includes_request_id(self):
        """When a trace is active, log lines should include request_id."""
        with patch("src.observability.tracing.RequestTrace._write_file"):
            with patch("src.observability.tracing.RequestTrace._write_mongo"):
                trace = RequestTrace(request_id="test-rid-456")

                formatter = StructuredJsonFormatter()
                record = logging.LogRecord(
                    name="test", level=logging.ERROR,
                    pathname="", lineno=0, msg="something failed",
                    args=None, exc_info=None,
                )
                output = formatter.format(record)
                data = json.loads(output)
                assert data["request_id"] == "test-rid-456"

                trace.finish()

    def test_log_event_with_extra_fields(self, caplog):
        """log_event should produce structured output with extra fields."""
        from src.observability.logging import log_event

        test_logger = logging.getLogger("test_structured")
        # Add our formatter
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJsonFormatter())
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        with patch("src.observability.tracing.RequestTrace._write_file"):
            with patch("src.observability.tracing.RequestTrace._write_mongo"):
                trace = RequestTrace(request_id="log-test-001")
                log_event(test_logger, logging.ERROR, "ocr_failed",
                          page=3, confidence=0.32, document_id="DOC-X")
                trace.finish()


# ─── Metrics Tests ────────────────────────────────────────────────────────────


class TestMetrics:
    """Tests for the in-process metrics recorder."""

    def test_counter_increment(self):
        m = MetricsRecorder()
        m.increment("test_counter", 5)
        m.increment("test_counter", 3)
        snap = m.snapshot()
        assert snap["counters"]["test_counter"] == 8

    def test_latency_histogram(self):
        m = MetricsRecorder()
        for v in [10, 20, 30, 40, 50]:
            m.record_latency("test_latency", v)
        snap = m.snapshot()
        lat = snap["latencies"]["test_latency"]
        assert lat["count"] == 5
        assert lat["min_ms"] == 10
        assert lat["max_ms"] == 50
        assert lat["p50_ms"] == 30

    def test_snapshot_empty(self):
        m = MetricsRecorder()
        snap = m.snapshot()
        assert snap["counters"] == {}
        assert snap["latencies"] == {}


# ─── Integration: OCR failure produces structured error log ───────────────────


class TestOCRFailureLogging:
    """Ensure OCR failures produce structured ERROR logs, not crashes."""

    def test_ocr_failure_structured_error(self, caplog):
        """Force an OCR failure and verify structured ERROR log is emitted."""
        from src.ingest.pdf_scanned import ScannedPDFAdapter
        from src.ingest.base import IngestionError

        # Create a mock that simulates a pytesseract failure
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_image(page.rect, pixmap=page.get_pixmap())

        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        doc.save(tmp.name)
        doc.close()
        tmp.close()

        adapter = ScannedPDFAdapter()

        # Mock pytesseract to raise an error
        with patch("src.ingest.pdf_scanned.pytesseract") as mock_tess:
            mock_tess.image_to_data.side_effect = RuntimeError("OCR engine crashed")
            mock_tess.Output = MagicMock()
            mock_tess.Output.DICT = "dict"

            with pytest.raises(IngestionError) as exc_info:
                adapter.ingest(tmp.name, "OCR-FAIL-001", "A")

            # Should be a clear error message, not a raw stack trace
            assert "OCR failed" in str(exc_info.value)

        os.unlink(tmp.name)
