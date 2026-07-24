# Delta Chat — Full Explanation (Simple Language)

## What is this app?

Imagine you're an engineer working on a chemical plant. You have a big technical drawing (called a P&ID) that shows all the pipes, valves, compressors, and instruments. Now your colleague makes changes to this drawing — maybe they changed a pressure value from 45 to 48, or added a new safety valve.

**The problem:** These drawings are huge and complex. Finding what changed between version A and version B by eye is tedious, error-prone, and slow.

**Delta Chat solves this.** You upload two versions of a document, and the system:
1. Reads both documents (even if they're scanned images)
2. Figures out exactly what changed (what was added, removed, or modified)
3. Shows you a clear report of all changes
4. Lets you ASK QUESTIONS about the changes in plain English, and the AI only answers from what's actually in your documents (no making stuff up)

---

## Why is it called "Delta Chat"?

- **Delta (Δ)** = the Greek letter engineers use to mean "change" or "difference"
- **Chat** = you can chat with an AI about those differences

So: "Chat about the differences" = Delta Chat.

---

## What can it read?

| Document Type | What it means | How it works |
|---|---|---|
| **Native PDF** | A normal PDF where you can select/copy text | Reads text directly from the file, very accurate |
| **Scanned PDF** | A PDF that's actually a photo/scan of paper | Uses OCR (like reading a photo) to extract text — less accurate but still works |
| **DXF file** | A CAD drawing file (engineering software) | Reads directly using a library |
| **DWG file** | Another CAD format (needs special software to convert first) | Converts to DXF then reads |

---

## How does the whole thing work? (Step by step)

### Step 1: Upload Documents

You give the system two files:
- **Document A** = the "old" version (base)
- **Document B** = the "new" version (revised)

For each file, you also give it a name (like "PID-EGC-001") and a revision label (like "A" or "B").

### Step 2: Ingestion (Reading the documents)

The system reads each document and breaks it into **elements** — each element is a piece of text on the page, along with:
- The actual text content (e.g., "Suction Pressure: 45.2 barg")
- Where it is on the page (coordinates/bounding box)
- What type of thing it is (a number, an equipment tag, a note, etc.)
- How confident the system is about reading it correctly (100% for native PDF, lower for OCR scans)

This produces a **Canonical Document** — a standardized representation that looks the same regardless of whether the original was a PDF, a scan, or a CAD file.

### Step 3: Comparison (Finding the differences)

The **Delta Engine** takes both Canonical Documents and compares them element by element:

1. **Exact matching:** For each element in Doc B, look for an identical element in Doc A. If found = no change.
2. **Fuzzy matching:** For unmatched elements, check if there's a "similar" element (like "Duty: 776 kW" vs "Duty: 800 kW" — same structure, different number). If similarity > 70% = **modified**.
3. **Remaining unmatched in Doc B** = **added** (new stuff)
4. **Remaining unmatched in Doc A** = **removed** (deleted stuff)

Each detected change gets:
- A type (added / removed / modified)
- The old value and new value
- The page number and exact location
- A confidence score (how sure is the system)
- A description

### Step 4: Report Generation

The system produces:
- A **JSON report** (structured data, machine-readable)
- A **Markdown report** (human-readable, with tables and sections)
- Both are saved to the database AND to files

### Step 5: Chat (Ask questions)

Now comes the AI part. You can type a question like "What happened to the suction pressure?"

Here's what happens behind the scenes:
1. **Retrieval:** The system searches through chunks of your documents and the delta report to find the most relevant pieces of information
2. **Prompt building:** Those chunks are packaged into a prompt with strict instructions: "ONLY answer from these chunks, cite your sources"
3. **LLM call:** The prompt is sent to Google's Gemini AI (via OpenRouter)
4. **Citation verification:** The system checks that the AI's citations are real (not made up)
5. **Response:** You get an answer + a list of sources (like "PID_A, Page 1" or "Delta Report")

If the AI can't find the answer in the documents, it says: "I could not find sufficient evidence..." — it NEVER makes stuff up.

### Step 6: Markup (Visual highlighting)

You can download an annotated PDF where changes are highlighted with colored boxes:
- 🟢 Green = added
- 🔴 Red = removed
- 🟡 Amber = modified

---

## What's running under the hood?

The app has 4 Docker containers running together:

| Container | What it does |
|---|---|
| **Backend** (Python/FastAPI) | The brain — does all the processing, comparison, AI calls |
| **Frontend** (React/Vite) | The website you see in your browser |
| **MySQL** | Stores structured data (document records, change records, eval scores) |
| **MongoDB** | Stores big documents (full canonical documents, chunks, reports, traces) |

---

## Where is everything stored?

| Data | Where | Why there |
|---|---|---|
| Full document content | MongoDB `canonical_documents` | Documents are big and nested |
| Summary records | MySQL `documents` table | Easy to query/filter |
| Delta report | MongoDB `delta_reports` | Full JSON is nested/complex |
| Individual changes | MySQL `delta_records` | Easy to count/filter/score |
| Text chunks for chat | MongoDB `chunks` | Flexible structure |
| Request traces | MongoDB `traces` + JSON files | Debugging |
| LLM call logs | MongoDB `llm_calls` | Full prompt/response for debugging |
| Eval results | MySQL `eval_runs` + JSON files | Scoring |

---

## Observability (How you debug problems)

Every request to the system gets a unique **request_id**. This ID appears in:
- The API response (JSON body + HTTP header)
- The trace file (`outputs/traces/{request_id}.json`)
- Every log line generated during that request
- The MongoDB trace record

If something goes wrong, you can take the request_id and find the complete story of what happened: what stages ran, how long each took, what the LLM was asked and what it returned, where it failed.

---

## Evaluation (Is the system actually correct?)

The system has a built-in evaluation harness that tests itself against documents with KNOWN correct answers:

- 3 synthetic document pairs with deliberate, documented changes
- Ground truth: "we changed the duty from 776 kW to 800 kW" — did the engine detect it?
- Scores: Precision (how many detected changes are real), Recall (how many real changes were detected), F1 (combined score)

Current scores:
- **Recall: 100%** — it finds ALL the real changes
- **Precision: 60-83%** — some false positives (mostly from OCR noise and revision metadata)
- **Chat correctness: 75%** — the AI answers correctly 75% of the time

---

## The Commands You Need

```bash
# Start everything
make up

# Seed sample data and run the pipeline
make run

# Run tests (96 automated tests)
make test

# Run evaluation harness
make eval

# Stop everything
make down
```

---

---

# Video Demo Script (Detailed Steps)

## Before Recording

1. Make sure Docker Desktop is running
2. Open terminal in the `delta-chat` folder
3. Run `make up` and wait until you see all 4 containers "Healthy"
4. Open browser to `http://localhost:3000`

---

## Recording Steps

### Scene 1: Landing Page (0:00 - 0:20)

**What to show:** The browser at http://localhost:3000

**What to say:**
"This is Delta Chat — a tool that compares engineering document revisions and lets you ask AI-powered questions about what changed. Let me show you how it works."

**What to point out:**
- The app name and tagline
- The 4-step flow diagram (Ingest → Delta Engine → Report → Chat)
- The green "Online" status dot in the top right (shows the system is healthy)
- The light mode design (and click the moon icon to show dark mode exists)

---

### Scene 2: Upload Documents (0:20 - 0:50)

**What to do:**
1. Click "Compare" in the nav bar (or the "Start Comparing" button)
2. On the left dropzone ("Document A"), drag in `Export Gas Compressor-P&ID (1).pdf`
3. Type `PID-EGC-001` in the Document ID field, type `A` in Revision
4. Click "Upload & Ingest" — wait for the green checkmark and "native_pdf" badge
5. On the right dropzone ("Document B"), drag in `Lift Gas compressor-P&ID.pdf`
6. Type `PID-LGC-001` in the Document ID field, type `A` in Revision
7. Click "Upload & Ingest" — wait for the green checkmark

**What to say:**
"I'm uploading two P&ID documents — an Export Gas Compressor and a Lift Gas Compressor. The system detects these are native PDFs with extractable text. Each gets a unique ID and revision label."

---

### Scene 3: Run Comparison (0:50 - 1:15)

**What to do:**
1. Click the blue "Compare Documents" button
2. Show the loading stages appearing (Detecting Changes...)
3. Wait for results to appear

**What to say:**
"The delta engine is now comparing every text element between these two documents — matching by content, using fuzzy matching to detect modifications. This takes less than a second."

**What to point out:**
- Summary cards: "254 Added, 74 Removed, 245 Modified"
- Click "Modified" filter button to filter the list
- Expand one change to show old value → new value (e.g., "26-PDI-9015" → "26-PDI-9054")
- The confidence percentage on each change

---

### Scene 4: Download Reports (1:15 - 1:30)

**What to do:**
1. Click "↓ Markdown" button → show the markdown report opening
2. Click "🖍 Markup A" button → show the annotated PDF downloading (changes highlighted)

**What to say:**
"You can download the comparison as a Markdown report or as an annotated PDF with colored highlights showing where changes are on the page."

---

### Scene 5: Chat (1:30 - 2:15)

**What to do:**
1. Click "Ask about these docs →" button
2. You land on the Chat page with the document pair pre-filled
3. Notice the "Previous Comparisons" dropdown is populated
4. Click the example question: "What changed between the two documents?"
5. Wait for the AI response
6. Show the citation pill(s) below the answer
7. Show the token/cost display
8. Type a specific question: "What is the compressor tag for the 3rd stage HP gas export compressor?"
9. Show the grounded answer with citation

**What to say:**
"Now I can ask questions about these documents in plain English. The AI retrieves relevant chunks from both documents and the delta report, then answers ONLY from that evidence. See the citation — it tells me exactly where in the document this information comes from. It never makes things up."

10. Type a question the system can't answer: "What is the weather today?"
11. Show the fallback message

**What to say:**
"And when the AI doesn't have enough evidence, it says so clearly rather than hallucinating an answer."

---

### Scene 6: Previous Comparisons (2:15 - 2:30)

**What to do:**
1. Navigate back to "/compare"
2. Scroll down to show "Previous Comparisons" section
3. Show the cards with past pairs and their change counts
4. Click "Ask questions about this pair →" on one

**What to say:**
"All comparisons are saved. You can come back later and continue asking questions about any previously compared pair."

---

### Scene 7: Evaluation (2:30 - 3:00)

**What to do:**
1. Click "Evaluation" in the nav
2. Show the metrics dashboard (counters, latencies)
3. Switch to terminal
4. Run: `make eval`
5. Show the scorecard output

**What to say:**
"The system has a built-in evaluation harness. It tests against 3 synthetic document pairs with known correct answers. Recall is 100% — it catches every real change. Precision is 60% — there are some false positives, especially from scanned documents where OCR introduces noise. This is documented honestly."

**What to point out in the terminal output:**
- "Precision: 0.60, Recall: 1.00, F1: 0.75"
- "Chat Correctness: 75%"
- The FAILURES section showing specific false positives

---

### Scene 8: Observability (3:00 - 3:20)

**What to do:**
1. In terminal, run: `docker compose logs backend --tail=5`
2. Show structured JSON log lines with request_id
3. Run: `docker compose exec backend cat outputs/traces/<some-request-id>.json`
4. Show the trace JSON with stages and timing

**What to say:**
"Every request is fully traced — structured JSON logs with correlation IDs, per-stage timing, token counts, and cost estimates. You can debug any request after the fact."

---

### Scene 9: Wrap-up (3:20 - 3:40)

**What to do:**
1. Show the terminal: `make test` (briefly, just show "96 passed")
2. Show the GitHub repo page

**What to say:**
"96 automated tests, full Docker Compose orchestration, CI workflow, and honest evaluation with real failure cases documented. That's Delta Chat — compare engineering documents, see what changed, and ask questions grounded in the evidence."

---

## Tips for the Recording

- Use a screen recorder like QuickTime (Cmd+Shift+5 on Mac)
- Record at 1920x1080 if possible
- Keep the browser zoomed to ~110% so text is readable
- Have both PDFs ready on your Desktop for easy drag-and-drop
- Run `make up && make run` BEFORE starting the recording so data is pre-seeded
- The Chat responses take 2-3 seconds (LLM latency) — that's normal, don't cut it
- If any step shows an error, just explain it and move on — the eval section honestly shows failures anyway
