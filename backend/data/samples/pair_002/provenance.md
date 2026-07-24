# Pair 002 — Provenance

This is a synthetically authored document pair created for evaluation purposes; it is not a real engineering document. Field naming conventions and units were referenced from publicly uploaded 26-KA-901/26-KA-902 P&ID excerpts for realism only.

## Description

**Equipment:** 26-VL-301 HP 3-Phase Separator (fictional)  
**Format:** Both base.pdf and revised.pdf are native text-searchable PDFs.

## Intentional Changes (Rev A → Rev B)

| # | Type | Old Value | New Value |
|---|------|-----------|-----------|
| 1 | Modified | `LIC-201 LEVEL CONTROLLER` | `LIC-201A LEVEL CONTROLLER` |
| 2 | Modified | `Normal Operating Level: 60 %` | `Normal Operating Level: 55 %` |
| 3 | Modified | `Operating Pressure: 32 barg` | `Operating Pressure: 35 barg` |
| 4 | Added | — | `PSV-205 RELIEF VALVE SET 52 BARG` |
| 5 | Added | — | `NOTE 6: HIGH-HIGH LEVEL INITIATES ESD` |
| 6 | Removed | `MANUAL DRAIN VALVE DN50` | — |

## Shifted-Line Scenario

In the revised version, `NOTE 6: HIGH-HIGH LEVEL INITIATES ESD` is inserted between NOTE 2 and NOTE 3. This pushes NOTE 3 and NOTE 4 to new positions (y-offset changes). The delta engine must not falsely report NOTE 3 and NOTE 4 as modified — they are merely repositioned, with identical text content. The alignment logic handles this correctly via content matching regardless of position.

## Known False Positive

The delta engine will also detect `Rev: A` → `Rev: B` as a "modified" change (revision metadata, not an engineering change).
