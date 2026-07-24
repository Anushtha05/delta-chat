"""Delta engine — compares two CanonicalDocuments and produces DeltaRecords.

This is a basic element-matching comparison engine that identifies added, removed,
and modified elements between two document revisions. It uses normalized_content
for matching and fuzzy matching (rapidfuzz) for detecting modifications.

Matching strategy:
1. Build a lookup of elements in doc_a by (page, normalized_content).
2. For each element in doc_b, try to find an exact match in doc_a (same page + content).
3. Exact matches are ignored (no change).
4. Unmatched elements in doc_b → check for fuzzy matches among unmatched doc_a elements
   on the same page. If ratio > 70%, classify as "modified". Otherwise → "added".
5. Remaining unmatched elements in doc_a → "removed".
"""

import uuid
from datetime import datetime, timezone

from rapidfuzz import fuzz

from src.canonical.model import CanonicalDocument, Element
from src.delta.model import DeltaRecord


def _build_element_key(elem: Element) -> str:
    """Create a matching key from page + normalized content."""
    return f"{elem.page_number}::{elem.normalized_content or elem.content.lower()}"


def compare_documents(
    doc_a: CanonicalDocument,
    doc_b: CanonicalDocument,
    fuzzy_threshold: float = 70.0,
) -> list[DeltaRecord]:
    """Compare two canonical documents and return a list of DeltaRecords.

    Args:
        doc_a: The base/reference document (older revision).
        doc_b: The compared document (newer revision).
        fuzzy_threshold: Minimum fuzzy match ratio (0-100) to consider a modification
                         vs. an addition/removal pair.

    Returns:
        List of DeltaRecord instances representing all detected changes.
    """
    records: list[DeltaRecord] = []
    now = datetime.now(timezone.utc)

    # Collect all elements from both documents
    elements_a: list[Element] = []
    elements_b: list[Element] = []
    for page in doc_a.pages:
        elements_a.extend(page.elements)
    for page in doc_b.pages:
        elements_b.extend(page.elements)

    # Build index for doc_a: key -> list of elements (handles duplicates)
    a_by_key: dict[str, list[Element]] = {}
    for elem in elements_a:
        key = _build_element_key(elem)
        a_by_key.setdefault(key, []).append(elem)

    # Track which doc_a elements have been matched
    matched_a_ids: set[str] = set()
    unmatched_b: list[Element] = []

    # Phase 1: Exact matching
    for elem_b in elements_b:
        key = _build_element_key(elem_b)
        candidates = a_by_key.get(key, [])
        matched = False
        for candidate in candidates:
            if candidate.id not in matched_a_ids:
                matched_a_ids.add(candidate.id)
                matched = True
                break
        if not matched:
            unmatched_b.append(elem_b)

    # Collect unmatched doc_a elements
    unmatched_a = [e for e in elements_a if e.id not in matched_a_ids]

    # Phase 2: Fuzzy matching for modifications
    # Group unmatched elements by page for efficiency
    unmatched_a_by_page: dict[int, list[Element]] = {}
    for elem in unmatched_a:
        unmatched_a_by_page.setdefault(elem.page_number, []).append(elem)

    fuzzy_matched_a_ids: set[str] = set()
    still_unmatched_b: list[Element] = []

    for elem_b in unmatched_b:
        page_candidates = unmatched_a_by_page.get(elem_b.page_number, [])
        best_match: Element | None = None
        best_ratio: float = 0.0

        norm_b = elem_b.normalized_content or elem_b.content.lower()

        for candidate in page_candidates:
            if candidate.id in fuzzy_matched_a_ids:
                continue
            norm_a = candidate.normalized_content or candidate.content.lower()
            ratio = fuzz.ratio(norm_a, norm_b)
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = candidate

        if best_match and best_ratio >= fuzzy_threshold:
            # Modified element
            fuzzy_matched_a_ids.add(best_match.id)
            records.append(
                DeltaRecord(
                    change_id=str(uuid.uuid4()),
                    document_a=doc_a.document_id,
                    document_b=doc_b.document_id,
                    change_type="modified",
                    element_type=elem_b.type,
                    page=elem_b.page_number,
                    old_value=best_match.content,
                    new_value=elem_b.content,
                    description=f"Content modified (similarity: {best_ratio:.0f}%)",
                    confidence=round(best_ratio / 100.0, 4),
                    bbox_a=best_match.bbox,
                    bbox_b=elem_b.bbox,
                    created_at=now,
                )
            )
        else:
            still_unmatched_b.append(elem_b)

    # Phase 3: Remaining unmatched → added/removed
    for elem_b in still_unmatched_b:
        records.append(
            DeltaRecord(
                change_id=str(uuid.uuid4()),
                document_a=doc_a.document_id,
                document_b=doc_b.document_id,
                change_type="added",
                element_type=elem_b.type,
                page=elem_b.page_number,
                old_value=None,
                new_value=elem_b.content,
                description=f"Element added in document B (page {elem_b.page_number})",
                confidence=elem_b.confidence,
                bbox_a=None,
                bbox_b=elem_b.bbox,
                created_at=now,
            )
        )

    # Remaining unmatched doc_a elements (not fuzzy-matched either) → removed
    final_removed_a = [
        e for e in unmatched_a if e.id not in fuzzy_matched_a_ids
    ]
    for elem_a in final_removed_a:
        records.append(
            DeltaRecord(
                change_id=str(uuid.uuid4()),
                document_a=doc_a.document_id,
                document_b=doc_b.document_id,
                change_type="removed",
                element_type=elem_a.type,
                page=elem_a.page_number,
                old_value=elem_a.content,
                new_value=None,
                description=f"Element removed from document A (page {elem_a.page_number})",
                confidence=elem_a.confidence,
                bbox_a=elem_a.bbox,
                bbox_b=None,
                created_at=now,
            )
        )

    return records
