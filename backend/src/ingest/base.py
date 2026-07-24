"""Abstract base class for document format adapters.

Every supported document format implements FormatAdapter. The registry
iterates adapters in priority order and uses the first one whose
can_handle() returns True.
"""

from abc import ABC, abstractmethod

from src.canonical.model import CanonicalDocument


class FormatAdapter(ABC):
    """Interface that all ingestion adapters must implement."""

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Return True if this adapter can process the given file.

        Implementations may inspect the file extension and/or peek at
        the file content (e.g., checking for a text layer in PDFs).
        """
        ...

    @abstractmethod
    def ingest(self, file_path: str, document_id: str, revision: str) -> CanonicalDocument:
        """Parse the file and return a CanonicalDocument.

        Args:
            file_path: Absolute path to the file on disk.
            document_id: The PID (Persistent Identifier) for this document.
            revision: The revision string (e.g., "A", "B", "01").

        Returns:
            A fully populated CanonicalDocument.

        Raises:
            IngestionError: If the file cannot be parsed.
        """
        ...


class IngestionError(Exception):
    """Raised when a document cannot be ingested due to format or content issues."""
    pass


class DWGConversionUnavailable(IngestionError):
    """Raised when ODA File Converter is not available for DWG→DXF conversion."""
    pass


class UnsupportedFormatError(IngestionError):
    """Raised when no adapter can handle the given file."""
    pass
