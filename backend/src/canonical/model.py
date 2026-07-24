"""Canonical document model for delta-chat ingestion pipeline.

All document formats (native PDF, scanned PDF, DWG/DXF) are normalized into
this single model before any downstream processing (comparison, chat, etc.).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Element(BaseModel):
    """A single extractable element from a document page."""

    id: str
    type: Literal[
        "text",
        "note",
        "dimension",
        "technical_value",
        "table_cell",
        "geometry",
        "equipment",
        "instrument",
    ]
    content: str
    normalized_content: str | None = None
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    page_number: int
    confidence: float = 1.0
    source_format: Literal["native_pdf", "scanned_pdf", "dwg"]
    extra: dict = Field(default_factory=dict)


class Page(BaseModel):
    """A single page of a document with its dimensions and extracted elements."""

    page_number: int
    width: float
    height: float
    elements: list[Element]


class CanonicalDocument(BaseModel):
    """The top-level canonical representation of an ingested document.

    document_id is the PID (Persistent Identifier) — NOT a P&ID reference.
    """

    document_id: str
    revision: str
    format: Literal["native_pdf", "scanned_pdf", "dwg"]
    source_filename: str
    ingested_at: datetime
    pages: list[Page]
    metadata: dict = Field(default_factory=dict)
