# Demo Script (2–4 minutes)

## 0:00 — Introduction

"This is Delta Chat — an engineering document comparison system. I'll walk through the complete pipeline: ingesting two P&ID revisions, detecting changes, asking grounded questions with citations, and validating with the evaluation harness."

## 0:20 — Start the Stack

```bash
make up
```

Show the terminal: Docker Compose brings up 4 services (backend, frontend, MySQL, MongoDB). All report healthy within ~30 seconds. Open `http://localhost:3000` — the landing page loads with the system status indicator showing green "Online".

## 0:40 — Document Comparison

Navigate to `/compare` in the UI. Upload two PDF files:
- **Document A**: Export Gas Compressor P&ID (Rev A)
- **Document B**: Lift Gas Compressor P&ID (Rev A)

Fill in document IDs (`PID-EGC-001`, `PID-LGC-001`) and revisions. Click "Upload & Ingest" on each. The format badge appears ("native_pdf").

Click "Compare Documents". The loading stages progress: Ingesting → Detecting Changes → Done.

## 1:10 — Delta Report

The results appear:
- **Summary cards**: 254 Added, 74 Removed, 245 Modified (573 total changes)
- **Filterable list**: Click "Modified" filter to see modifications. Expand a row to see old value → new value with confidence score.

Example: `26-PDI-9015 HH INITIATE PRESSURIZED COMPRESSOR STOP` → `26-PDI-9054 HH INITIATE PRESSURIZED COMPRESSOR STOP` (98% confidence).

Click "Download Markdown" to open the full report. Show the structured markdown with summary table and grouped changes.

## 1:50 — Grounded Chat

Click "Ask about these docs" button — navigates to `/chat` with the document pair pre-filled.

Click the example chip "What changed?" or type: "What is the compressor tag for the 3rd stage HP gas export compressor?"

The assistant responds with the answer and a citation pill: `[PID_A, Page 1, "M 26-KA-902 3RD STAGE HP GAS EXPORT COMP..."]`. Token count and cost shown below.

Ask an unsupported question: "What is the weather today?" — system responds with the fallback: "I could not find sufficient evidence in PID A, PID B, or the delta report to answer this confidently."

## 2:30 — Evaluation

Navigate to `/evaluation`. The metrics dashboard shows pipeline counters and latency stats.

In terminal, run:
```bash
make eval
```

The scorecard prints: Precision 0.60, Recall 1.00, F1 0.75. Chat correctness 75%. Known failures listed (Rev metadata false positives, OCR noise).

## 3:00 — Observability

Show a trace file:
```bash
docker compose exec backend cat outputs/traces/<request_id>.json
```

Show the structured JSON with endpoint, stages (retrieval: 28ms, LLM: 2444ms), metadata (chunks_retrieved, input_tokens, estimated_cost).

Show structured logs:
```bash
docker compose logs backend --tail=5
```

Every line is JSON with timestamp, level, event, request_id correlation.

## 3:30 — Wrap-up

"The system detects all intentional engineering changes with 100% recall. Precision is 83% for native PDFs — the false positives are trivial metadata changes. For scanned PDFs, OCR noise reduces precision to 11% — a known limitation documented in the README. The grounded chat refuses to hallucinate and cites its sources. The full test suite is 94 tests, all passing."
