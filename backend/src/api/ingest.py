"""Document ingestion API endpoint.

POST /api/documents/ingest — multipart file upload with document_id and revision fields.
Runs the full ingestion pipeline and returns a summary response.
"""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.ingest.base import IngestionError, UnsupportedFormatError
from src.ingest.registry import registry
from src.ingest.persist import persist
from src.observability.tracing import RequestTrace
from src.observability.metrics import metrics
from src.observability.logging import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["ingestion"])


@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    document_id: str = Form(...),
    revision: str = Form(...),
):
    """Ingest an uploaded document file."""
    trace = RequestTrace()
    trace.endpoint = "POST /api/documents/ingest"

    if not file.filename:
        trace.finish("error")
        raise HTTPException(status_code=400, detail="No filename provided.")

    suffix = Path(file.filename).suffix
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            if not content:
                trace.finish("error")
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            tmp.write(content)
            tmp_path = tmp.name
    except HTTPException:
        raise
    except Exception as e:
        trace.finish("error")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    try:
        with trace.stage("ingestion") as stage:
            stage.set("document_id", document_id)
            stage.set("revision", revision)
            stage.set("filename", file.filename)
            stage.set("file_size_bytes", len(content))

            canonical_doc = registry.ingest_file(tmp_path, document_id, revision)
            persist_result = persist(canonical_doc)

            total_elements = sum(len(p.elements) for p in canonical_doc.pages)
            stage.set("format", canonical_doc.format)
            stage.set("page_count", len(canonical_doc.pages))
            stage.set("element_count", total_elements)

        # Metrics
        metrics.record_latency("ingestion", stage.duration_ms)
        metrics.increment("ingestion_count")

        log_event(logger, logging.INFO, "ingestion_complete",
                  document_id=document_id, revision=revision,
                  format=canonical_doc.format, duration_ms=stage.duration_ms)

        # Build summary response
        first_elements = []
        for page in canonical_doc.pages:
            for elem in page.elements[:5]:
                first_elements.append(elem.model_dump(mode="json"))
                if len(first_elements) >= 10:
                    break
            if len(first_elements) >= 10:
                break

        trace_data = trace.finish("success")

        response_body = {
            "status": "ingested",
            "request_id": trace.request_id,
            "document_id": canonical_doc.document_id,
            "revision": canonical_doc.revision,
            "format": canonical_doc.format,
            "source_filename": canonical_doc.source_filename,
            "page_count": len(canonical_doc.pages),
            "element_count": total_elements,
            "mongo_id": persist_result["mongo_id"],
            "mysql_id": persist_result["mysql_id"],
            "sample_elements": first_elements,
        }

        return JSONResponse(
            content=response_body,
            headers={"X-Request-Id": trace.request_id},
        )

    except UnsupportedFormatError as e:
        log_event(logger, logging.ERROR, "ingestion_unsupported_format",
                  document_id=document_id, error_detail=str(e))
        trace.finish("error")
        raise HTTPException(status_code=415, detail=str(e))
    except IngestionError as e:
        log_event(logger, logging.ERROR, "ingestion_failed",
                  document_id=document_id, error_type=type(e).__name__,
                  error_detail=str(e))
        trace.finish("error")
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        trace.finish("error")
        raise
    except Exception as e:
        log_event(logger, logging.ERROR, "ingestion_unexpected_error",
                  document_id=document_id, error_type=type(e).__name__,
                  error_detail=str(e))
        trace.finish("error")
        raise HTTPException(status_code=500, detail=f"Internal ingestion error: {type(e).__name__}")
    finally:
        try:
            os.unlink(tmp_path)
        except (OSError, UnboundLocalError):
            pass
