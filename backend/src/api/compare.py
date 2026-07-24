"""Document comparison API endpoints.

POST /api/compare — run delta engine on two ingested documents, persist results
GET /api/compare/{doc_a_id}/{doc_b_id} — retrieve stored JSON report
GET /api/compare/{doc_a_id}/{doc_b_id}/report.md — retrieve stored markdown report
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from src.canonical.model import CanonicalDocument
from src.chat.chunker import chunk_delta_records, chunk_document, store_chunks
from src.delta.engine import compare_documents
from src.delta.persist import persist_all
from src.delta.report import generate_json_report, generate_markdown_report
from src.observability.tracing import RequestTrace
from src.observability.metrics import metrics
from src.observability.logging import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compare", tags=["comparison"])


class CompareRequest(BaseModel):
    """Request body for POST /api/compare."""
    document_a_id: str
    revision_a: str
    document_b_id: str
    revision_b: str


def _fetch_canonical_doc(document_id: str, revision: str) -> CanonicalDocument:
    """Fetch a CanonicalDocument from MongoDB by document_id + revision."""
    from src.db.mongo import get_db

    db = get_db()
    collection = db["canonical_documents"]

    doc_data = collection.find_one(
        {"document_id": document_id, "revision": revision}
    )

    if not doc_data:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id} rev {revision}. "
                   f"Ensure it has been ingested first via POST /api/documents/ingest.",
        )

    doc_data.pop("_id", None)
    return CanonicalDocument(**doc_data)


@router.post("")
def run_comparison(request: CompareRequest):
    """Compare two ingested documents and return the delta report."""
    trace = RequestTrace()
    trace.endpoint = "POST /api/compare"

    try:
        with trace.stage("delta") as stage:
            stage.set("document_a_id", request.document_a_id)
            stage.set("document_b_id", request.document_b_id)

            doc_a = _fetch_canonical_doc(request.document_a_id, request.revision_a)
            doc_b = _fetch_canonical_doc(request.document_b_id, request.revision_b)

            delta_records = compare_documents(doc_a, doc_b)

            stage.set("changes_found", len(delta_records))
            stage.set("added", len([r for r in delta_records if r.change_type == "added"]))
            stage.set("removed", len([r for r in delta_records if r.change_type == "removed"]))
            stage.set("modified", len([r for r in delta_records if r.change_type == "modified"]))

            doc_a_meta = {
                "document_id": doc_a.document_id,
                "revision": doc_a.revision,
                "format": doc_a.format,
                "source_filename": doc_a.source_filename,
                "page_count": len(doc_a.pages),
                "element_count": sum(len(p.elements) for p in doc_a.pages),
            }
            doc_b_meta = {
                "document_id": doc_b.document_id,
                "revision": doc_b.revision,
                "format": doc_b.format,
                "source_filename": doc_b.source_filename,
                "page_count": len(doc_b.pages),
                "element_count": sum(len(p.elements) for p in doc_b.pages),
            }

            json_report = generate_json_report(delta_records, doc_a_meta, doc_b_meta)
            markdown_report = generate_markdown_report(json_report)

            persist_result = persist_all(
                json_report=json_report,
                markdown_report=markdown_report,
                delta_records=delta_records,
                document_a_id=request.document_a_id,
                document_b_id=request.document_b_id,
            )

            chunks_a = chunk_document(doc_a, "PID_A")
            chunks_b = chunk_document(doc_b, "PID_B")
            chunks_delta = chunk_delta_records(delta_records, request.document_a_id, request.document_b_id)
            all_chunks = chunks_a + chunks_b + chunks_delta
            store_chunks(all_chunks)

            stage.set("chunks_stored", len(all_chunks))

        # Metrics
        metrics.record_latency("delta", stage.duration_ms)
        metrics.increment("delta_count")
        metrics.increment("delta_added", stage.metadata.get("added", 0))
        metrics.increment("delta_removed", stage.metadata.get("removed", 0))
        metrics.increment("delta_modified", stage.metadata.get("modified", 0))

        log_event(logger, logging.INFO, "comparison_complete",
                  document_id=f"{request.document_a_id}_vs_{request.document_b_id}",
                  changes_found=len(delta_records), duration_ms=stage.duration_ms)

        json_report["_persistence"] = persist_result
        json_report["_chunks_stored"] = len(all_chunks)
        json_report["request_id"] = trace.request_id

        trace.finish("success")

        return JSONResponse(
            content=json_report,
            headers={"X-Request-Id": trace.request_id},
        )

    except HTTPException:
        trace.finish("error")
        raise
    except Exception as e:
        log_event(logger, logging.ERROR, "comparison_failed",
                  error_type=type(e).__name__, error_detail=str(e))
        trace.finish("error")
        raise HTTPException(status_code=500, detail=f"Comparison error: {type(e).__name__}")


@router.get("/{document_a_id}/{document_b_id}")
def get_json_report(document_a_id: str, document_b_id: str):
    """Retrieve the stored JSON delta report for a document pair."""
    from src.db.mongo import get_db

    db = get_db()
    collection = db["delta_reports"]

    report = collection.find_one(
        {"document_a.document_id": document_a_id, "document_b.document_id": document_b_id}
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No delta report found for {document_a_id} vs {document_b_id}. "
                   f"Run POST /api/compare first.",
        )

    report.pop("_id", None)
    return report


@router.get("/{document_a_id}/{document_b_id}/report.md")
def get_markdown_report(document_a_id: str, document_b_id: str):
    """Retrieve the stored Markdown delta report for a document pair."""
    outputs_dir = Path(__file__).resolve().parent.parent.parent / "outputs" / "reports"
    safe_a = document_a_id.replace("/", "_").replace(" ", "_")
    safe_b = document_b_id.replace("/", "_").replace(" ", "_")
    md_path = outputs_dir / f"{safe_a}_vs_{safe_b}.md"

    if md_path.is_file():
        content = md_path.read_text(encoding="utf-8")
        return PlainTextResponse(content, media_type="text/markdown")

    from src.db.mongo import get_db

    db = get_db()
    collection = db["delta_reports"]

    report = collection.find_one(
        {"document_a.document_id": document_a_id, "document_b.document_id": document_b_id}
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No delta report found for {document_a_id} vs {document_b_id}.",
        )

    report.pop("_id", None)
    markdown = generate_markdown_report(report)
    return PlainTextResponse(markdown, media_type="text/markdown")


@router.get("/{document_a_id}/{document_b_id}/markup")
def get_markup_pdf(document_a_id: str, document_b_id: str, doc: str = "a"):
    """Return an annotated PDF with delta change highlights overlaid.

    Query param `doc=a` for base document markup, `doc=b` for revised.
    """
    from fastapi.responses import Response
    from src.db.mongo import get_db
    from src.canonical.model import CanonicalDocument as CanDoc
    from src.delta.model import DeltaRecord
    from src.markup.overlay import render_markup

    if doc not in ("a", "b"):
        raise HTTPException(status_code=400, detail="Query param 'doc' must be 'a' or 'b'.")

    db = get_db()

    # Get the report to find delta records
    report = db["delta_reports"].find_one(
        {"document_a.document_id": document_a_id, "document_b.document_id": document_b_id}
    )
    if not report:
        raise HTTPException(status_code=404, detail="No delta report found. Run POST /api/compare first.")

    # Determine which document to annotate
    target_doc_id = document_a_id if doc == "a" else document_b_id
    # Find the canonical document to get revision
    canon_data = db["canonical_documents"].find_one({"document_id": target_doc_id})
    if not canon_data:
        raise HTTPException(status_code=404, detail=f"Document {target_doc_id} not found in MongoDB.")

    canon_data.pop("_id", None)
    canonical_doc = CanDoc(**canon_data)

    # Rebuild delta records from the report's changes
    records = []
    for c in report.get("changes", []):
        records.append(DeltaRecord(
            change_id=c.get("change_id", ""),
            document_a=document_a_id,
            document_b=document_b_id,
            change_type=c["change_type"],
            element_type=c.get("element_type", "text"),
            page=c.get("page", 1),
            old_value=c.get("old_value"),
            new_value=c.get("new_value"),
            description=c.get("description", ""),
            confidence=c.get("confidence", 1.0),
            bbox_a=tuple(c["bbox_a"]) if c.get("bbox_a") else None,
            bbox_b=tuple(c["bbox_b"]) if c.get("bbox_b") else None,
        ))

    # We need the original PDF file path — for Docker, use the ingested temp or stored path
    # Since we don't store the original file, we'll re-create a PDF from the canonical doc
    # for overlay purposes. This works because our synthetic PDFs are reproducible.
    import tempfile
    import fitz

    # Create a temporary PDF from the canonical document's content for annotation
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf_doc = fitz.open()
    for page_data in canonical_doc.pages:
        page = pdf_doc.new_page(width=page_data.width, height=page_data.height)
        for elem in page_data.elements:
            if elem.content.strip():
                x0, y0, _, _ = elem.bbox
                try:
                    page.insert_text((x0, y0 + 10), elem.content, fontsize=9)
                except Exception:
                    pass
    pdf_doc.save(tmp.name)
    pdf_doc.close()
    tmp.close()

    try:
        annotated_bytes = render_markup(canonical_doc, records, tmp.name, side=doc)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        import os
        os.unlink(tmp.name)

    filename = f"{target_doc_id}_markup.pdf"
    return Response(
        content=annotated_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
