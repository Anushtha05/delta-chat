# Delta Chat

**Engineering document revision comparison with grounded AI chat.**

Compare P&ID/data-sheet revisions (PDF, scanned PDF, DWG/DXF), see exactly what changed at the element level, and ask questions that are answered only from the evidence — with citations.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React/Vite)                     │
│   Landing · Compare · Chat · Evaluation   :3000                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │ REST API
┌─────────────────────▼───────────────────────────────────────────┐
│                     Backend (FastAPI/Python)           :8000     │
│                                                                 │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Ingest   │→ │ Delta      │→ │ Report   │→ │ Chat (RAG)  │  │
│  │ Adapters │  │ Engine     │  │ Gen      │  │ + LLM       │  │
│  └──────────┘  └────────────┘  └──────────┘  └─────────────┘  │
│       │              │               │              │           │
│  ┌────▼──────────────▼───────────────▼──────────────▼────┐     │
│  │              Observability (Tracing/Logs/Metrics)      │     │
│  └───────────────────────────────────────────────────────┘     │
└──────────┬─────────────────────────────────┬───────────────────┘
           │                                 │
    ┌──────▼──────┐                  ┌───────▼───────┐
    │   MySQL     │                  │    MongoDB    │
    │  Structured │                  │   Documents   │
    │  Queries    │                  │   Chunks      │
    └─────────────┘                  └───────────────┘
```

## Supported Formats

| Format | Status | Details |
|--------|--------|---------|
| **Native PDF** | ✅ Full | Text extraction via PyMuPDF. Element-level bboxes, type classification. |
| **Scanned PDF** | ✅ Full | OCR via pytesseract (Tesseract required). Confidence scores per element. |
| **DWG/DXF** | ⚠️ Best-effort | DXF parsed directly via ezdxf. DWG requires ODA File Converter (external download from opendesign.com). Set `ODA_CONVERTER_PATH` env var. Raises a clear error if ODA is missing — never fails silently. |

All formats produce the same `CanonicalDocument` model via a single `FormatAdapter` interface. Adding a 4th format requires only implementing `can_handle()` + `ingest()` and registering in the adapter registry.

## Setup

```bash
git clone https://github.com/Anushtha05/delta-chat.git
cd delta-chat
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY (get from openrouter.ai)
# All other values have working defaults for local dev
```

Requirements: Docker + Docker Compose.

## Run

```bash
# 1. Start all services (backend, frontend, MySQL, MongoDB)
make up

# 2. Seed sample data + run full pipeline (ingest 3 pairs, compare, produce reports)
make run

# 3. Run evaluation harness
make eval

# 4. Open the UI
open http://localhost:3000
```

**The reviewer workflow is: `make up` → wait for healthy → `make run` → `make eval`.** Zero manual steps beyond starting Docker. All 3 synthetic pairs are ingested, compared, and evaluated automatically.

### Manual upload via curl:

```bash
curl -X POST http://localhost:8000/api/documents/ingest \
  -F "file=@your_document.pdf" \
  -F "document_id=MY-DOC-001" \
  -F "revision=A"
```

## Chat

Example interaction (real output from the system with `google/gemini-2.5-flash`):

```
Q: "In document PID-EGC-001, what is the compressor tag for the 3rd stage HP gas export compressor?"

A: "The compressor tag for the 3rd stage HP gas export compressor in document PID-EGC-001 is 26-KA-902."

Sources: [PID_A, Page 1, "M 26-KA-902 3RD STAGE HP GAS EXPORT COMP..."]
Tokens: 9438 in + 63 out · ~$0.0015
```

When the answer can't be grounded in the evidence:
```
"I could not find sufficient evidence in PID A, PID B, or the delta report to answer this confidently."
```

## Evaluation

```bash
make eval
```

Real scorecard from the 3 synthetic pairs:

```
========================================
DOCUMENT DELTA EVALUATION
========================================
Dataset: 3 pairs, 15 expected changes, 8 chat questions

DELTA METRICS
-------------
Precision: 0.60
Recall:    1.00
F1:        0.75

CHAT METRICS
------------
Correctness: 75.0%
Groundedness: 75.0%
Citation Accuracy: 75.0%

FAILURES
---------
  FALSE_POS [pair_001] modified: 'Rev: 0' → 'Rev: 1'
  FALSE_POS [pair_002] modified: 'Rev: A' → 'Rev: B'
  FALSE_POS [pair_003] modified: 'DESIGN DATA' → 'DESIGN'  (OCR noise)
========================================
```

## Observability

| What | Where |
|------|-------|
| Request traces | `outputs/traces/{request_id}.json` + MongoDB `traces` collection |
| Structured logs | stdout (JSON format), every line has `request_id` for correlation |
| Metrics | `GET /api/metrics` — counters + p50/p95 latencies per stage |
| LLM calls | MongoDB `llm_calls` — full prompt/response for debugging |
| Cost estimation | Configurable $/1K-token rates in config; logged per request |

Every response includes `X-Request-Id` header + `request_id` in the JSON body.

## Design Decisions

**Why MySQL + MongoDB split?** MySQL for structured queries (document metadata, delta records for scoring, eval runs) where you want JOINs and aggregations. MongoDB for document-shaped data (full canonical documents, chunks, reports, traces) where the schema is nested and varies by format.

**Why deterministic delta separate from LLM narrative?** The delta engine produces exact, reproducible, auditable changes with no LLM involved. The optional `/explain` endpoint adds an LLM summary stored in a separate field (`llm_summary`) — never overwrites the deterministic descriptions. This means the core comparison is debuggable without needing to reason about LLM behavior.

**Why OpenRouter/Gemini behind an LLMClient interface?** The abstract `LLMClient` class means swapping providers (OpenAI direct, Anthropic, local models) requires only a new implementation — no downstream changes. OpenRouter gives access to multiple models with one API key.

**Why keyword+fuzzy retrieval instead of embeddings?** For this scope (hundreds of chunks, not millions), a rapidfuzz partial_ratio + technical keyword boost retriever is fast, deterministic, requires no external vector DB or embedding model, and performs well on engineering text where the important tokens are numbers and instrument tags. The `Retriever` interface is there for a future embedding swap.

## Trade-offs

- **OCR comparison produces many false positives.** When comparing a native PDF against a scanned PDF, OCR line fragmentation creates noise. The engine still catches the real changes (recall=1.0) but precision drops (~11% for OCR pairs). A production system would need OCR post-processing or image-level alignment.
- **Chat correctness depends on the LLM model.** The grounded chat system enforces citation discipline, but smaller models sometimes return the fallback message even when the evidence is in the retrieved chunks. Gemini 2.5 Flash performs better than GPT-4o-mini for structured output compliance.
- **No embedding-based retrieval.** The fuzzy keyword retriever works for the current corpus size but would need replacement for large document sets.

## Known Failures (from real eval data)

1. **Rev metadata false positive:** Every native pair produces one spurious "Rev: A → Rev: B" change. The engine correctly detects it, but it's metadata not engineering content.
2. **OCR fragmentation:** Pair 003 (scanned revised) produces ~32 false positives from OCR breaking lines differently than the original text layout.
3. **Chat groundedness <100%:** The LLM sometimes answers correctly from context but doesn't comply with the JSON citation format, resulting in answers without verifiable chunk_ids.
4. **"CHECK VALVE CV-501 INSTALLED DOWNSTREAM" not detected as single add:** OCR fragments this note into multiple tokens, so it appears as several small adds rather than one clean addition.

## Future Improvements

- Embedding-based retrieval (FAISS/Qdrant) for larger document corpora
- OCR post-processing: line reassembly, spell correction against engineering dictionaries
- Phase 11 delta markup overlay (visual side-by-side highlighting)
- Multi-page document alignment (currently page-to-page, no cross-page matching)
- Streaming chat responses
- Role-based access control
- Cost budgeting with per-request token limits

## Testing

```bash
make test   # 94 tests, runs in Docker
```

Covers: ingestion (all 3 formats), canonical model validation, delta engine (numeric detection, determinism, alignment regression), report generation, grounded chat (mocked LLM), observability (tracing, logging, metrics), and end-to-end evaluation against real synthetic pairs.

## Project Structure

```
delta-chat/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI endpoints
│   │   ├── canonical/    # Document model
│   │   ├── chat/         # LLM, retriever, grounded answers
│   │   ├── delta/        # Comparison engine, reports
│   │   ├── ingest/       # Format adapters (PDF, OCR, DWG)
│   │   ├── db/           # MySQL + MongoDB clients
│   │   └── observability/# Tracing, logging, metrics
│   ├── eval/             # Evaluation harness
│   ├── tests/            # 94 pytest tests
│   └── data/samples/     # Synthetic eval pairs
├── frontend/             # React + Vite + Tailwind
├── docker-compose.yml
├── Makefile
└── .github/workflows/ci.yml
```
