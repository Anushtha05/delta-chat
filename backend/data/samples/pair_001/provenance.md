# Pair 001 — Provenance

This is a synthetically authored document pair created for evaluation purposes; it is not a real engineering document. Field naming conventions and units were referenced from publicly uploaded 26-KA-901/26-KA-902 P&ID excerpts for realism only.

## Description

**Equipment:** 26-KC-501 Export Gas Compressor (fictional)  
**Format:** Both base.pdf and revised.pdf are native text-searchable PDFs.

## Intentional Changes (Rev 0 → Rev 1)

| # | Type | Old Value | New Value |
|---|------|-----------|-----------|
| 1 | Modified | `Rated Duty: 776 kW` | `Rated Duty: 800 kW` |
| 2 | Modified | `Suction Pressure: 45.2 barg` | `Suction Pressure: 48.0 barg` |
| 3 | Modified | `26-KC-501` | `26-KC-501A` |
| 4 | Added | — | `NOTE 5: VSD MOTOR CONTROL REQUIRED` |
| 5 | Removed | `NOTE 4: TEMPORARY BYPASS LINE IN SERVICE` | — |

## Known False Positive

The delta engine will also detect `Rev: 0` → `Rev: 1` as a "modified" change. This is correct detection of a real text difference, but it is revision metadata rather than an engineering change, so it is NOT included in the evaluation ground truth.
