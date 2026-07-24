"""Document chunker for retrieval-augmented chat.

Produces retrieval chunks from:
1. CanonicalDocuments — one chunk per page (concatenated element contents)
2. DeltaRecords — one chunk per change record

All chunks are stored in MongoDB collection `chunks` for vector search / retrieval.
"""

import logging
import uuid
from typing import Literal

from src.canonical.model import CanonicalDocument
from src.delta.model import DeltaRecord

logger = logging.getLogger(__name__)


def _bbox_union(bboxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    """Compute the union bounding box enclosing all given bboxes."""
    if not bboxes:
        return (0.0, 0.0, 0.0, 0.0)
    x0 = min(b[0] for b in bboxes)
    y0 = min(b[1] for b in bboxes)
    x1 = max(b[2] for b in bboxes)
    y1 = max(b[3] for b in bboxes)
    return (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))


def chunk_document(
    doc: CanonicalDocument,
    source_label: Literal["PID_A", "PID_B"],
) -> list[dict]:
    """Chunk a CanonicalDocument into retrieval chunks — one per page.

    Each chunk contains:
    - chunk_id: unique identifier
    - source: "PID_A" or "PID_B"
    - document_id: the document's PID
    - page: page number
    - text: concatenated element contents (newline-separated)
    - bbox_union: bounding box enclosing all elements on the page
    - delta_change_id: None (not a delta chunk)
    """
    chunks: list[dict] = []

    for page in doc.pages:
        if not page.elements:
            continue

        text_parts = [elem.content for elem in page.elements if elem.content.strip()]
        if not text_parts:
            continue

        bboxes = [elem.bbox for elem in page.elements]

        chunk = {
            "chunk_id": str(uuid.uuid4()),
            "source": source_label,
            "document_id": doc.document_id,
            "page": page.page_number,
            "text": "\n".join(text_parts),
            "bbox_union": list(_bbox_union(bboxes)),
            "delta_change_id": None,
        }
        chunks.append(chunk)

    return chunks


def chunk_delta_records(
    records: list[DeltaRecord],
    document_a_id: str,
    document_b_id: str,
) -> list[dict]:
    """Chunk delta records — one chunk per DeltaRecord.

    Each chunk contains:
    - chunk_id: unique identifier
    - source: "DELTA_REPORT"
    - document_id: "{document_a_id}_vs_{document_b_id}"
    - page: page where the change was detected
    - text: human-readable summary of the change
    - bbox_union: bbox from the changed element (B side if available, else A)
    - delta_change_id: the DeltaRecord's change_id
    """
    chunks: list[dict] = []

    for record in records:
        # Build a readable text representation of this change
        parts = [
            f"Change: {record.change_type}",
            f"Type: {record.element_type}",
            f"Page: {record.page}",
        ]
        if record.old_value:
            parts.append(f"Old: {record.old_value}")
        if record.new_value:
            parts.append(f"New: {record.new_value}")
        if record.description:
            parts.append(f"Description: {record.description}")

        text = "\n".join(parts)

        # Use the bbox from whichever side is available (prefer B for context)
        bbox = record.bbox_b or record.bbox_a or (0.0, 0.0, 0.0, 0.0)

        chunk = {
            "chunk_id": str(uuid.uuid4()),
            "source": "DELTA_REPORT",
            "document_id": f"{document_a_id}_vs_{document_b_id}",
            "page": record.page,
            "text": text,
            "bbox_union": list(bbox),
            "delta_change_id": record.change_id,
        }
        chunks.append(chunk)

    return chunks


def store_chunks(chunks: list[dict]) -> int:
    """Store chunks in MongoDB collection `chunks`.

    Uses bulk insert. Returns count of inserted chunks.
    """
    if not chunks:
        return 0

    from src.db.mongo import get_db

    db = get_db()
    collection = db["chunks"]

    # Remove existing chunks for the same document_id + source to avoid duplicates
    seen_keys: set[tuple[str, str]] = set()
    for chunk in chunks:
        key = (chunk["document_id"], chunk["source"])
        if key not in seen_keys:
            seen_keys.add(key)
            collection.delete_many({"document_id": chunk["document_id"], "source": chunk["source"]})

    result = collection.insert_many(chunks)
    count = len(result.inserted_ids)
    logger.info("Stored %d chunks in MongoDB", count)
    return count
