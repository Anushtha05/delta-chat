"""History API — list previously compared document pairs.

GET /api/compare/history — returns all past comparisons for browsing.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/compare", tags=["history"])


@router.get("/history")
def list_comparisons():
    """Return a list of all previously compared document pairs."""
    from src.db.mongo import get_db

    db = get_db()
    collection = db["delta_reports"]

    reports = collection.find(
        {},
        {
            "document_a.document_id": 1,
            "document_a.revision": 1,
            "document_b.document_id": 1,
            "document_b.revision": 1,
            "generated_at": 1,
            "summary": 1,
            "_id": 0,
        },
    ).sort("generated_at", -1).limit(50)

    results = []
    for r in reports:
        results.append({
            "document_a_id": r.get("document_a", {}).get("document_id", ""),
            "revision_a": r.get("document_a", {}).get("revision", ""),
            "document_b_id": r.get("document_b", {}).get("document_id", ""),
            "revision_b": r.get("document_b", {}).get("revision", ""),
            "generated_at": r.get("generated_at", ""),
            "summary": r.get("summary", {}),
        })

    return {"comparisons": results}
