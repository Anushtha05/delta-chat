"""Delta record model — represents a single change between two document revisions."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DeltaRecord(BaseModel):
    """A single detected change between document A and document B."""

    change_id: str
    document_a: str  # document_id of the base document
    document_b: str  # document_id of the compared document
    change_type: Literal["added", "removed", "modified"]
    element_type: str  # type from Element (text, equipment, instrument, etc.)
    page: int
    old_value: str | None = None  # content from doc A (None for 'added')
    new_value: str | None = None  # content from doc B (None for 'removed')
    description: str = ""
    confidence: float = 1.0
    bbox_a: tuple[float, float, float, float] | None = None
    bbox_b: tuple[float, float, float, float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
