"""Generate synthetic PDF pairs for evaluation.

Creates 3 pairs of PDFs in backend/data/samples/pair_XXX/ with known, controlled
differences. Ground truth is in eval/datasets/delta_cases.json.

Pair 001: Compressor data sheet — technical value modifications, tag change,
          added note, removed note.
Pair 002: Separator P&ID — instrument tag change, operating parameter changes,
          added safety device, removed item, PLUS a "shifted line" scenario
          (new note inserted between existing fields in revised version).
Pair 003: Cooling water system — same as before BUT revised.pdf is a SCANNED
          PDF (image-only, no text layer) to exercise the OCR path.

Run: python -m eval.generate_synthetic
"""

import os
from pathlib import Path

import fitz  # PyMuPDF

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"


def _create_native_pdf(texts: list[tuple[str, tuple[float, float], float]], filepath: Path) -> str:
    """Create a native (text-searchable) PDF.

    Args:
        texts: List of (content, (x, y), fontsize) tuples.
        filepath: Full output path.

    Returns:
        String path to the created file.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=841.89, height=595.28)  # A4 landscape

    for content, pos, fontsize in texts:
        page.insert_text(pos, content, fontsize=fontsize)

    doc.save(str(filepath))
    doc.close()
    return str(filepath)


def _create_scanned_pdf(texts: list[tuple[str, tuple[float, float], float]], filepath: Path) -> str:
    """Create a scanned (image-only) PDF — renders text to image, embeds as image.

    This exercises the OCR path during ingestion.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # First create a native PDF in memory
    source_doc = fitz.open()
    source_page = source_doc.new_page(width=841.89, height=595.28)
    for content, pos, fontsize in texts:
        source_page.insert_text(pos, content, fontsize=fontsize)

    # Render to high-DPI image (200 DPI for readable OCR)
    mat = fitz.Matrix(200 / 72, 200 / 72)
    pix = source_page.get_pixmap(matrix=mat)
    source_doc.close()

    # Create image-only PDF (no text layer)
    img_doc = fitz.open()
    img_page = img_doc.new_page(width=841.89, height=595.28)
    img_page.insert_image(img_page.rect, pixmap=pix)
    img_doc.save(str(filepath))
    img_doc.close()

    return str(filepath)


def generate_pair_001():
    """Pair 001: 26-KC-501 Export Gas Compressor Data Sheet.

    Fictional compressor. Changes from base (Rev 0) → revised (Rev 1):
    - MODIFIED: "Rated Duty: 776 kW" → "Rated Duty: 800 kW"
    - MODIFIED: "Suction Pressure: 45.2 barg" → "Suction Pressure: 48.0 barg"
    - MODIFIED: "26-KC-501" → "26-KC-501A"  (equipment tag updated)
    - ADDED: "NOTE 5: VSD MOTOR CONTROL REQUIRED" (new note in revised)
    - REMOVED: "NOTE 4: TEMPORARY BYPASS LINE IN SERVICE" (removed in revised)

    Both are native (text-searchable) PDFs.
    """
    # Elements shared between both revisions (unchanged content)
    common = [
        ("COMPRESSOR DATA SHEET", (300, 40), 14),
        ("Drawing: 26-DS-001", (50, 70), 10),
        ("Client: Delta Energy Corp", (50, 90), 9),
        ("Service: Export Gas Compression", (50, 110), 10),
        ("DESIGN CONDITIONS", (50, 150), 11),
        ("Design Pressure: 120 barg", (50, 175), 10),
        ("Design Temperature: 85 deg C", (50, 195), 10),
        ("Gas Molecular Weight: 19.5", (50, 215), 10),
        ("OPERATING CONDITIONS", (50, 255), 11),
        ("Discharge Pressure: 95 barg", (50, 295), 10),
        ("Discharge Temperature: 72 deg C", (50, 315), 10),
        ("Flow Rate: 15.2 MMSCFD", (50, 335), 10),
        ("Speed: 11000 RPM", (50, 355), 10),
        ("INSTRUMENTATION", (450, 150), 11),
        ("TIC-302 TEMPERATURE CONTROLLER", (450, 175), 10),
        ("FIC-401 FLOW CONTROLLER", (450, 195), 10),
        ("PIC-502 PRESSURE CONTROLLER", (450, 215), 10),
        ("XV-100 SUCTION ISOLATION VALVE", (450, 235), 10),
        ("NOTE 1: REFER TO VENDOR MANUAL FOR LUBE OIL SPECS", (50, 430), 9),
        ("NOTE 2: ALL INSTRUMENTS TO BE SIL-2 RATED", (50, 450), 9),
        ("NOTE 3: ANTI-SURGE SYSTEM PER API 670", (50, 470), 9),
    ]

    # Base-specific elements (Rev 0)
    base_only = [
        ("26-KC-501", (300, 60), 11),
        ("Rated Duty: 776 kW", (50, 275), 10),
        ("Suction Pressure: 45.2 barg", (50, 375), 10),
        ("NOTE 4: TEMPORARY BYPASS LINE IN SERVICE", (50, 490), 9),
        ("Rev: 0", (750, 560), 9),
    ]

    # Revised-specific elements (Rev 1)
    revised_only = [
        ("26-KC-501A", (300, 60), 11),
        ("Rated Duty: 800 kW", (50, 275), 10),
        ("Suction Pressure: 48.0 barg", (50, 375), 10),
        ("NOTE 5: VSD MOTOR CONTROL REQUIRED", (50, 490), 9),
        ("Rev: 1", (750, 560), 9),
    ]

    _create_native_pdf(common + base_only, SAMPLES_DIR / "pair_001" / "base.pdf")
    _create_native_pdf(common + revised_only, SAMPLES_DIR / "pair_001" / "revised.pdf")


def generate_pair_002():
    """Pair 002: 26-VL-301 HP Separator P&ID.

    Fictional separator. Changes from base (Rev A) → revised (Rev B):
    - MODIFIED: "LIC-201 LEVEL CONTROLLER" → "LIC-201A LEVEL CONTROLLER"
    - MODIFIED: "Normal Operating Level: 60 %" → "Normal Operating Level: 55 %"
    - MODIFIED: "Operating Pressure: 32 barg" → "Operating Pressure: 35 barg"
    - ADDED: "PSV-205 RELIEF VALVE SET 52 BARG" (new safety device in revised)
    - REMOVED: "MANUAL DRAIN VALVE DN50" (removed in revised)

    Additionally, this pair has a "shifted line" scenario: in the revised version,
    a new note "NOTE 6: HIGH-HIGH LEVEL INITIATES ESD" is inserted between
    NOTE 2 and NOTE 3, pushing subsequent notes down. This exercises alignment.

    Both are native (text-searchable) PDFs.
    """
    common = [
        ("P&ID - HP 3-PHASE SEPARATOR", (280, 40), 14),
        ("Drawing: 26-PID-002", (50, 70), 10),
        ("26-VL-301", (350, 60), 11),
        ("Service: HP Production Separation", (50, 110), 10),
        ("DESIGN DATA", (50, 150), 11),
        ("Design Pressure: 55 barg", (50, 175), 10),
        ("Design Temperature: 120 deg C", (50, 195), 10),
        ("Vessel Diameter: 2400 mm ID", (50, 215), 10),
        ("Tan-Tan Length: 7200 mm", (50, 235), 10),
        ("NOZZLES", (450, 150), 11),
        ("N1 Gas Outlet: DN200", (450, 175), 10),
        ("N2 Oil Outlet: DN150", (450, 195), 10),
        ("N3 Water Outlet: DN100", (450, 215), 10),
        ("N4 Inlet: DN250", (450, 235), 10),
        ("PIC-202 PRESSURE CONTROLLER", (450, 290), 10),
        ("TI-203 TEMPERATURE INDICATOR", (450, 310), 10),
        ("NOTE 1: INTERNAL COALESCING PLATES FITTED", (50, 420), 9),
        ("NOTE 2: SAND JET SYSTEM ACTIVE", (50, 440), 9),
    ]

    # Base-specific (Rev A) — notes 3 and 4 follow note 2 directly
    base_only = [
        ("LIC-201 LEVEL CONTROLLER", (450, 270), 10),
        ("Normal Operating Level: 60 %", (50, 275), 10),
        ("Operating Pressure: 32 barg", (50, 295), 10),
        ("MANUAL DRAIN VALVE DN50", (50, 375), 10),
        ("NOTE 3: VESSEL TO BE HYDROTEST AT 82.5 BARG", (50, 460), 9),
        ("NOTE 4: REFER TO CAUSE AND EFFECT CHART", (50, 480), 9),
        ("Rev: A", (750, 560), 9),
    ]

    # Revised-specific (Rev B) — "shifted line" scenario:
    # New NOTE 6 inserted between NOTE 2 and the old NOTE 3
    revised_only = [
        ("LIC-201A LEVEL CONTROLLER", (450, 270), 10),
        ("Normal Operating Level: 55 %", (50, 275), 10),
        ("Operating Pressure: 35 barg", (50, 295), 10),
        ("PSV-205 RELIEF VALVE SET 52 BARG", (50, 375), 10),
        ("NOTE 6: HIGH-HIGH LEVEL INITIATES ESD", (50, 460), 9),
        ("NOTE 3: VESSEL TO BE HYDROTEST AT 82.5 BARG", (50, 480), 9),
        ("NOTE 4: REFER TO CAUSE AND EFFECT CHART", (50, 500), 9),
        ("Rev: B", (750, 560), 9),
    ]

    _create_native_pdf(common + base_only, SAMPLES_DIR / "pair_002" / "base.pdf")
    _create_native_pdf(common + revised_only, SAMPLES_DIR / "pair_002" / "revised.pdf")


def generate_pair_003():
    """Pair 003: 26-PA-101 Cooling Water Pump P&ID.

    Fictional pump. Changes from base (Rev 0) → revised (Rev 1):
    - MODIFIED: "Rated Flow: 250 m3/h" → "Rated Flow: 280 m3/h"
    - MODIFIED: "Return Temperature: 45 deg C" → "Return Temperature: 42 deg C"
    - MODIFIED: "26-PA-101" → "26-PA-101B" (pump tag)
    - ADDED: "NOTE 3: CHECK VALVE CV-501 INSTALLED DOWNSTREAM" (new note)
    - REMOVED: "NOTE 2: SUCTION STRAINER BASKET TYPE" (removed)

    IMPORTANT: revised.pdf is generated as a SCANNED PDF (image-only, no text layer)
    to exercise the OCR ingestion path.
    """
    common = [
        ("P&ID - COOLING WATER SYSTEM", (280, 40), 14),
        ("Drawing: 26-PID-003", (50, 70), 10),
        ("Service: Closed Loop Cooling Water", (50, 110), 10),
        ("DESIGN DATA", (50, 150), 11),
        ("Supply Temperature: 32 deg C", (50, 175), 10),
        ("Supply Pressure: 6.0 barg", (50, 195), 10),
        ("Heat Duty: 1500 kW", (50, 215), 10),
        ("INSTRUMENTS", (450, 150), 11),
        ("FI-601 FLOW INDICATOR", (450, 175), 10),
        ("TI-602 SUPPLY TEMP INDICATOR", (450, 195), 10),
        ("TI-603 RETURN TEMP INDICATOR", (450, 215), 10),
        ("PI-604 DISCHARGE PRESS INDICATOR", (450, 235), 10),
        ("NOTE 1: MAINTAIN MIN 2 BARG DIFFERENTIAL PRESSURE", (50, 420), 9),
    ]

    # Base-specific (Rev 0) — native PDF
    base_only = [
        ("26-PA-101", (350, 60), 11),
        ("Rated Flow: 250 m3/h", (50, 255), 10),
        ("Return Temperature: 45 deg C", (50, 275), 10),
        ("Differential Head: 35 m", (50, 295), 10),
        ("Motor Power: 55 kW", (50, 315), 10),
        ("NOTE 2: SUCTION STRAINER BASKET TYPE", (50, 440), 9),
        ("Rev: 0", (750, 560), 9),
    ]

    # Revised-specific (Rev 1) — will be rendered as SCANNED PDF
    revised_only = [
        ("26-PA-101B", (350, 60), 11),
        ("Rated Flow: 280 m3/h", (50, 255), 10),
        ("Return Temperature: 42 deg C", (50, 275), 10),
        ("Differential Head: 35 m", (50, 295), 10),
        ("Motor Power: 55 kW", (50, 315), 10),
        ("NOTE 3: CHECK VALVE CV-501 INSTALLED DOWNSTREAM", (50, 440), 9),
        ("Rev: 1", (750, 560), 9),
    ]

    _create_native_pdf(common + base_only, SAMPLES_DIR / "pair_003" / "base.pdf")
    # Revised is SCANNED (image-only) to exercise OCR
    _create_scanned_pdf(common + revised_only, SAMPLES_DIR / "pair_003" / "revised.pdf")


def main():
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    generate_pair_001()
    generate_pair_002()
    generate_pair_003()
    print(f"Generated 3 synthetic pairs in {SAMPLES_DIR}")
    print("  pair_001: native base.pdf + native revised.pdf")
    print("  pair_002: native base.pdf + native revised.pdf (with shifted-line scenario)")
    print("  pair_003: native base.pdf + SCANNED revised.pdf (OCR path)")


if __name__ == "__main__":
    main()
