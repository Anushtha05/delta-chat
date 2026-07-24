"""Adapter registry — selects the correct format adapter for a given file.

Adapters are tried in priority order:
1. NativePDFAdapter (checks for text layer)
2. ScannedPDFAdapter (fallback for PDFs without text layer)
3. DWGAdapter (DWG/DXF CAD files)

To add a new format, implement FormatAdapter and register it here.
"""

from src.canonical.model import CanonicalDocument
from src.ingest.base import FormatAdapter, UnsupportedFormatError
from src.ingest.dwg import DWGAdapter
from src.ingest.pdf_native import NativePDFAdapter
from src.ingest.pdf_scanned import ScannedPDFAdapter


class AdapterRegistry:
    """Holds all format adapters and routes files to the correct one."""

    def __init__(self) -> None:
        # Priority order: native PDF first (detects text layer), then scanned, then DWG
        self._adapters: list[FormatAdapter] = [
            NativePDFAdapter(),
            ScannedPDFAdapter(),
            DWGAdapter(),
        ]

    def register(self, adapter: FormatAdapter) -> None:
        """Register an additional adapter (appended to end of priority list)."""
        self._adapters.append(adapter)

    def get_adapter(self, file_path: str) -> FormatAdapter:
        """Find the first adapter that can handle the given file.

        Raises:
            UnsupportedFormatError: If no adapter can handle the file.
        """
        for adapter in self._adapters:
            if adapter.can_handle(file_path):
                return adapter
        raise UnsupportedFormatError(
            f"No adapter can handle file: {file_path}. "
            f"Supported formats: native PDF, scanned PDF, DWG, DXF."
        )

    def ingest_file(self, file_path: str, document_id: str, revision: str) -> CanonicalDocument:
        """Ingest a file using the appropriate adapter.

        This is the primary entry point for the ingestion pipeline.
        """
        adapter = self.get_adapter(file_path)
        return adapter.ingest(file_path, document_id, revision)


# Module-level singleton for convenience
registry = AdapterRegistry()
