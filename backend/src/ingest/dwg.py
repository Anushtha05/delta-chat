"""DWG/DXF adapter — extracts elements from CAD files.

For .dxf files: parses directly with ezdxf.
For .dwg files: converts to .dxf using ODA File Converter (path configurable
via ODA_CONVERTER_PATH env var), then parses the resulting .dxf.
"""

import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import ezdxf

from src.canonical.model import CanonicalDocument, Element, Page
from src.delta.normalize import normalize
from src.ingest.base import DWGConversionUnavailable, FormatAdapter, IngestionError


def _get_oda_path() -> str | None:
    """Get ODA File Converter path from environment or check common locations."""
    env_path = os.environ.get("ODA_CONVERTER_PATH", "")
    if env_path:
        return env_path

    # Common install locations
    common_paths = [
        "/usr/bin/ODAFileConverter",
        "/usr/local/bin/ODAFileConverter",
        "/opt/ODAFileConverter/ODAFileConverter",
        "C:\\Program Files\\ODA\\ODAFileConverter\\ODAFileConverter.exe",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p
    return None


def _convert_dwg_to_dxf(dwg_path: str) -> str:
    """Convert a .dwg file to .dxf using ODA File Converter.

    Returns the path to the temporary .dxf file.
    Raises DWGConversionUnavailable if ODA is not installed.
    """
    oda_path = _get_oda_path()
    if not oda_path or not os.path.isfile(oda_path):
        raise DWGConversionUnavailable(
            "ODA File Converter is not installed or not found. "
            "To convert .dwg files, install ODA File Converter from "
            "https://www.opendesign.com/guestfiles/oda_file_converter "
            "and set the ODA_CONVERTER_PATH environment variable to the "
            "executable path. Without it, only .dxf files can be processed."
        )

    input_dir = str(Path(dwg_path).parent)
    input_filename = Path(dwg_path).name
    output_dir = tempfile.mkdtemp(prefix="delta_chat_dxf_")

    # ODA File Converter CLI: input_dir output_dir output_version output_type recurse audit
    # Output ACAD2018 DXF format
    try:
        subprocess.run(
            [
                oda_path,
                input_dir,
                output_dir,
                "ACAD2018",
                "DXF",
                "0",  # no recursion
                "1",  # audit
                input_filename,
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        raise IngestionError(
            f"ODA File Converter failed: {e.stderr.decode(errors='replace')}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise IngestionError("ODA File Converter timed out after 120 seconds.") from e

    # Find the output .dxf file
    dxf_name = Path(dwg_path).stem + ".dxf"
    dxf_path = os.path.join(output_dir, dxf_name)
    if not os.path.isfile(dxf_path):
        raise IngestionError(
            f"ODA conversion completed but output file not found at {dxf_path}. "
            f"Contents of output dir: {os.listdir(output_dir)}"
        )
    return dxf_path


def _parse_dxf(dxf_path: str, source_filename: str, document_id: str,
               revision: str, source_format: str = "dwg") -> CanonicalDocument:
    """Parse a DXF file with ezdxf and extract elements."""
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as e:
        raise IngestionError(f"Failed to parse DXF file '{source_filename}': {e}") from e

    msp = doc.modelspace()
    elements: list[Element] = []

    for entity in msp:
        dxf_type = entity.dxftype()

        if dxf_type in ("TEXT", "MTEXT"):
            # Extract text entities
            if dxf_type == "TEXT":
                content = entity.dxf.text or ""
                insert = entity.dxf.insert
                # Use insertion point as a synthetic bbox (width estimated from text length)
                char_width = entity.dxf.height * 0.6  # approximate character width
                text_width = len(content) * char_width
                bbox = (
                    round(insert.x, 2),
                    round(insert.y, 2),
                    round(insert.x + text_width, 2),
                    round(insert.y + entity.dxf.height, 2),
                )
            else:  # MTEXT
                content = entity.plain_text() if hasattr(entity, "plain_text") else (entity.text or "")
                insert = entity.dxf.insert
                # MTEXT has a defined width
                width = getattr(entity.dxf, "width", 100.0) or 100.0
                height = getattr(entity.dxf, "char_height", 2.5) or 2.5
                bbox = (
                    round(insert.x, 2),
                    round(insert.y, 2),
                    round(insert.x + width, 2),
                    round(insert.y + height, 2),
                )

            if not content.strip():
                continue

            elements.append(
                Element(
                    id=str(uuid.uuid4()),
                    type="text",
                    content=content.strip(),
                    normalized_content=normalize(content.strip()),
                    bbox=bbox,
                    page_number=1,  # DXF/DWG is single "page" (model space)
                    confidence=1.0,
                    source_format="dwg",
                )
            )

        elif dxf_type in ("LINE", "CIRCLE", "ARC", "POLYLINE", "LWPOLYLINE",
                          "ELLIPSE", "SPLINE"):
            # Geometry entities — extract bounding box from extents
            try:
                if dxf_type == "LINE":
                    start = entity.dxf.start
                    end = entity.dxf.end
                    bbox = (
                        round(min(start.x, end.x), 2),
                        round(min(start.y, end.y), 2),
                        round(max(start.x, end.x), 2),
                        round(max(start.y, end.y), 2),
                    )
                elif dxf_type == "CIRCLE":
                    center = entity.dxf.center
                    r = entity.dxf.radius
                    bbox = (
                        round(center.x - r, 2),
                        round(center.y - r, 2),
                        round(center.x + r, 2),
                        round(center.y + r, 2),
                    )
                elif dxf_type == "ARC":
                    center = entity.dxf.center
                    r = entity.dxf.radius
                    bbox = (
                        round(center.x - r, 2),
                        round(center.y - r, 2),
                        round(center.x + r, 2),
                        round(center.y + r, 2),
                    )
                else:
                    # For polylines, ellipses, splines — skip bbox calculation
                    # to avoid complexity; use a zero-area placeholder
                    bbox = (0.0, 0.0, 0.0, 0.0)

                elements.append(
                    Element(
                        id=str(uuid.uuid4()),
                        type="geometry",
                        content=dxf_type,
                        normalized_content=dxf_type.lower(),
                        bbox=bbox,
                        page_number=1,
                        confidence=1.0,
                        source_format="dwg",
                        extra={"dxf_type": dxf_type},
                    )
                )
            except Exception:
                # Skip malformed geometry entities
                continue

    # DWG/DXF files don't have pages in the traditional sense.
    # We treat the entire model space as page 1.
    # Use a standard A1 sheet size as default if no layout info available.
    page_width = 841.0  # A1 width in mm
    page_height = 594.0  # A1 height in mm

    pages = [
        Page(
            page_number=1,
            width=page_width,
            height=page_height,
            elements=elements,
        )
    ]

    return CanonicalDocument(
        document_id=document_id,
        revision=revision,
        format="dwg",
        source_filename=source_filename,
        ingested_at=datetime.now(timezone.utc),
        pages=pages,
        metadata={"dxf_version": doc.dxfversion if hasattr(doc, "dxfversion") else "unknown"},
    )


class DWGAdapter(FormatAdapter):
    """Adapter for DWG and DXF CAD files."""

    def can_handle(self, file_path: str) -> bool:
        """Return True for .dwg and .dxf file extensions."""
        suffix = Path(file_path).suffix.lower()
        return suffix in (".dwg", ".dxf")

    def ingest(self, file_path: str, document_id: str, revision: str) -> CanonicalDocument:
        """Parse DWG/DXF file and return a CanonicalDocument."""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if not path.is_file():
            raise IngestionError(f"File not found: {file_path}")

        if suffix == ".dxf":
            return _parse_dxf(file_path, path.name, document_id, revision)
        elif suffix == ".dwg":
            # Convert to DXF first, then parse
            dxf_path = _convert_dwg_to_dxf(file_path)
            try:
                return _parse_dxf(dxf_path, path.name, document_id, revision)
            finally:
                # Clean up temp file
                try:
                    os.unlink(dxf_path)
                    os.rmdir(os.path.dirname(dxf_path))
                except OSError:
                    pass
        else:
            raise IngestionError(f"Unsupported CAD format: {suffix}")
