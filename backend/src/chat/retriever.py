"""Retrieval layer for grounded chat — keyword + fuzzy scoring over MongoDB chunks.

This is an in-process retriever that scores chunks from the `chunks` collection
using a combination of:
  (a) rapidfuzz partial_ratio between query and chunk text
  (b) keyword overlap boost for numeric/technical terms (engineering-relevant tokens)

Designed behind a Retriever interface so it can be swapped for a real embedding-based
retriever later without touching downstream code.
"""

import re
import logging
from abc import ABC, abstractmethod

from pydantic import BaseModel
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Technical terms that get a scoring boost when they appear in both query and chunk
_TECHNICAL_BOOST_WEIGHT = 15.0  # points added per matching technical keyword


def _extract_technical_terms(text: str) -> set[str]:
    """Extract numeric values and engineering-significant tokens from text.

    Captures: bare numbers, numbers with units (e.g. "150psi", "3.5mm"),
    tag patterns (e.g. "XV-100", "TIC-302"), and common engineering units.
    """
    terms: set[str] = set()

    # Numbers (with optional decimal)
    for m in re.finditer(r"\b\d+\.?\d*\b", text):
        terms.add(m.group())

    # Numbers+units run together (e.g. "150psi", "3.5bar")
    for m in re.finditer(r"\b\d+\.?\d*\s*(?:psi|bar|barg|kpa|mpa|mm|cm|m|in|ft|kg|lb|rpm|kw|hp|dn\d*)\b", text, re.IGNORECASE):
        terms.add(m.group().lower().replace(" ", ""))

    # Equipment/instrument tags (e.g. "XV-100", "26-PDI-9015")
    for m in re.finditer(r"\b[A-Z0-9]{1,4}[-/][A-Z0-9]{2,6}\b", text, re.IGNORECASE):
        terms.add(m.group().upper())

    # Engineering keywords
    eng_words = {"compressor", "pump", "valve", "pressure", "temperature", "flow",
                 "duty", "suction", "discharge", "inlet", "outlet", "separator",
                 "cooler", "heater", "vessel", "pipe", "flange", "nozzle"}
    for word in text.lower().split():
        clean = re.sub(r"[^\w]", "", word)
        if clean in eng_words:
            terms.add(clean)

    return terms


# ─── Interface ────────────────────────────────────────────────────────────────


class Chunk(BaseModel):
    """A retrieved chunk with its relevance score."""
    chunk_id: str
    source: str  # "PID_A", "PID_B", or "DELTA_REPORT"
    document_id: str
    page: int
    text: str
    bbox_union: list[float]
    delta_change_id: str | None = None
    score: float = 0.0


class Retriever(ABC):
    """Abstract retriever interface — swap implementations without changing callers."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        document_scope: list[str] | None = None,
        top_k: int = 6,
    ) -> list[Chunk]:
        """Retrieve top_k relevant chunks for the given query.

        Args:
            query: The user's question or search text.
            document_scope: Optional list of document_ids to restrict search.
                           If None, search across all chunks.
            top_k: Number of top-scoring chunks to return.
        """
        ...


# ─── Keyword + Fuzzy implementation ──────────────────────────────────────────


class KeywordFuzzyRetriever(Retriever):
    """In-process retriever using rapidfuzz + keyword boosting.

    Scores each chunk by:
    1. rapidfuzz.partial_ratio(query, chunk.text) → 0..100 base score
    2. +BOOST for each technical term shared between query and chunk

    No external vector DB required. Suitable for moderate corpus sizes
    (thousands of chunks). For larger corpora, swap for an embedding retriever.
    """

    def retrieve(
        self,
        query: str,
        document_scope: list[str] | None = None,
        top_k: int = 6,
    ) -> list[Chunk]:
        """Score and return top_k chunks from MongoDB."""
        from src.db.mongo import get_db

        db = get_db()
        collection = db["chunks"]

        # Build MongoDB filter
        mongo_filter: dict = {}
        if document_scope:
            mongo_filter["document_id"] = {"$in": document_scope}

        # Fetch candidate chunks
        cursor = collection.find(mongo_filter)
        candidates = list(cursor)

        if not candidates:
            logger.warning("No chunks found for scope=%s", document_scope)
            return []

        # Extract technical terms from query
        query_terms = _extract_technical_terms(query)
        query_lower = query.lower()

        # Score each chunk
        scored: list[tuple[float, dict]] = []
        for doc in candidates:
            chunk_text = doc.get("text", "")

            # Base score: fuzzy partial match
            base_score = fuzz.partial_ratio(query_lower, chunk_text.lower())

            # Technical keyword boost
            chunk_terms = _extract_technical_terms(chunk_text)
            overlap = query_terms & chunk_terms
            boost = len(overlap) * _TECHNICAL_BOOST_WEIGHT

            total_score = base_score + boost
            scored.append((total_score, doc))

        # Sort by score descending, take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        # Convert to Chunk models
        results: list[Chunk] = []
        for score, doc in top:
            results.append(Chunk(
                chunk_id=doc.get("chunk_id", ""),
                source=doc.get("source", ""),
                document_id=doc.get("document_id", ""),
                page=doc.get("page", 0),
                text=doc.get("text", ""),
                bbox_union=doc.get("bbox_union", [0, 0, 0, 0]),
                delta_change_id=doc.get("delta_change_id"),
                score=round(score, 2),
            ))

        return results
