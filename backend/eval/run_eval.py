"""Evaluation runner — orchestrates the full delta-chat evaluation.

Runs delta detection and chat scoring against ground-truth datasets,
prints a formatted scorecard, and persists results.

Run: python -m eval.run_eval
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import from the backend package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TESTING", "true")

from eval.metrics import score_delta, score_chat


DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "metrics"


def _load_json(filename: str) -> list[dict]:
    path = DATASETS_DIR / filename
    with open(path, "r") as f:
        return json.load(f)


def _ensure_synthetic_pairs():
    """Generate synthetic PDF pairs if they don't exist."""
    marker = SAMPLES_DIR / "pair_001" / "base.pdf"
    if not marker.exists():
        print("Generating synthetic PDF pairs...")
        from eval.generate_synthetic import main as gen_main
        gen_main()


def _ingest_document(file_path: str, document_id: str, revision: str):
    """Ingest a document using the same pipeline as the API."""
    from src.ingest.registry import registry
    from src.ingest.persist import persist

    canonical_doc = registry.ingest_file(file_path, document_id, revision)
    persist(canonical_doc)
    return canonical_doc


def _run_comparison(doc_a_id: str, rev_a: str, doc_b_id: str, rev_b: str):
    """Run comparison in-process (same as POST /api/compare)."""
    from src.db.mongo import get_db
    from src.canonical.model import CanonicalDocument
    from src.delta.engine import compare_documents
    from src.chat.chunker import chunk_delta_records, chunk_document, store_chunks

    db = get_db()
    collection = db["canonical_documents"]

    doc_a_data = collection.find_one({"document_id": doc_a_id, "revision": rev_a})
    doc_b_data = collection.find_one({"document_id": doc_b_id, "revision": rev_b})

    if not doc_a_data or not doc_b_data:
        raise RuntimeError(f"Documents not found: {doc_a_id}:{rev_a}, {doc_b_id}:{rev_b}")

    doc_a_data.pop("_id", None)
    doc_b_data.pop("_id", None)

    doc_a = CanonicalDocument(**doc_a_data)
    doc_b = CanonicalDocument(**doc_b_data)

    delta_records = compare_documents(doc_a, doc_b)

    # Store chunks for chat retrieval
    chunks_a = chunk_document(doc_a, "PID_A")
    chunks_b = chunk_document(doc_b, "PID_B")
    chunks_delta = chunk_delta_records(delta_records, doc_a_id, doc_b_id)
    store_chunks(chunks_a + chunks_b + chunks_delta)

    return delta_records


async def _run_chat_question(question: str, doc_a_id: str, doc_b_id: str) -> dict:
    """Run a chat question in-process (same as POST /api/chat)."""
    from src.chat.llm import get_llm_client, LLMRequestError
    from src.chat.retriever import KeywordFuzzyRetriever
    from src.chat.answer import generate_grounded_answer

    try:
        llm_client = get_llm_client()
    except (ValueError, SystemExit):
        return {"answer": "", "citations": [], "chunk_ids": [], "skipped": True}

    retriever = KeywordFuzzyRetriever()

    try:
        answer = await generate_grounded_answer(
            question=question,
            llm_client=llm_client,
            retriever=retriever,
            document_a_id=doc_a_id,
            document_b_id=doc_b_id,
        )
        return answer.model_dump()
    except LLMRequestError as e:
        return {"answer": f"LLM ERROR: {e}", "citations": [], "chunk_ids": [], "error": str(e)}


def _persist_results(results: dict):
    """Write results to outputs/metrics/ and MySQL."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = OUTPUTS_DIR / f"eval_{timestamp}.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults written to: {path}")

    # Try to persist to MySQL (may not be available in all environments)
    try:
        from src.db.mysql import _get_engine
        from sqlalchemy import text as sql_text, MetaData, Table, Column, Integer, Float, String, DateTime, Text
        engine = _get_engine()

        meta = MetaData()
        eval_table = Table(
            "eval_runs", meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("run_at", DateTime, nullable=False),
            Column("precision_score", Float),
            Column("recall_score", Float),
            Column("f1_score", Float),
            Column("chat_correctness", Float),
            Column("chat_groundedness", Float),
            Column("citation_accuracy", Float),
            Column("details_json", Text),
        )
        meta.create_all(engine, checkfirst=True)

        with engine.begin() as conn:
            conn.execute(eval_table.insert().values(
                run_at=datetime.now(timezone.utc),
                precision_score=results["delta_metrics"]["precision"],
                recall_score=results["delta_metrics"]["recall"],
                f1_score=results["delta_metrics"]["f1"],
                chat_correctness=results["chat_metrics"].get("correctness", 0),
                chat_groundedness=results["chat_metrics"].get("groundedness", 0),
                citation_accuracy=results["chat_metrics"].get("citation_accuracy", 0),
                details_json=json.dumps(results, default=str),
            ))
        print("Results persisted to MySQL eval_runs table.")
    except Exception as e:
        print(f"Warning: Could not persist to MySQL: {e}")


def main():
    """Run the full evaluation pipeline."""
    print("=" * 40)
    print("DOCUMENT DELTA EVALUATION")
    print("=" * 40)

    # Ensure synthetic data exists
    _ensure_synthetic_pairs()

    # Load datasets
    delta_cases = _load_json("delta_cases.json")
    qa_cases = _load_json("qa_cases.json")

    total_expected = sum(len(c["expected_changes"]) for c in delta_cases)
    print(f"\nDataset: {len(delta_cases)} pairs, {total_expected} expected changes, {len(qa_cases)} chat questions")

    # ─── Delta Evaluation ─────────────────────────────────────────────────
    all_matched = []
    all_false_positives = []
    all_missed = []
    total_precision_sum = 0.0
    total_recall_sum = 0.0

    for case in delta_cases:
        pair_id = case["pair_id"]
        doc_a_file = str(SAMPLES_DIR / case["doc_a_path"])
        doc_b_file = str(SAMPLES_DIR / case["doc_b_path"])
        doc_a_id = case.get("doc_a_id", f"EVAL-{pair_id}-A")
        doc_b_id = case.get("doc_b_id", f"EVAL-{pair_id}-B")

        print(f"\n  Processing {pair_id}...")

        # Ingest
        try:
            _ingest_document(doc_a_file, doc_a_id, "A")
            _ingest_document(doc_b_file, doc_b_id, "B")
        except Exception as e:
            print(f"    ERROR: Ingestion failed: {e}")
            continue

        # Compare
        try:
            delta_records = _run_comparison(doc_a_id, "A", doc_b_id, "B")
        except Exception as e:
            print(f"    ERROR: Comparison failed: {e}")
            continue

        # Score
        result = score_delta(case["expected_changes"], delta_records)
        print(f"    Changes detected: {len(delta_records)}, "
              f"Matched: {len(result['matched'])}, "
              f"Missed: {len(result['missed'])}, "
              f"FP: {len(result['false_positives'])}")
        print(f"    P={result['precision']:.3f} R={result['recall']:.3f} F1={result['f1']:.3f}")

        all_matched.extend(result["matched"])
        all_false_positives.extend(
            [{"pair_id": pair_id, **fp} for fp in result["false_positives"]]
        )
        all_missed.extend(
            [{"pair_id": pair_id, **m} for m in result["missed"]]
        )
        total_precision_sum += result["precision"]
        total_recall_sum += result["recall"]

    # Aggregate delta metrics
    n_pairs = len(delta_cases)
    agg_precision = total_precision_sum / n_pairs if n_pairs > 0 else 0
    agg_recall = total_recall_sum / n_pairs if n_pairs > 0 else 0
    agg_f1 = (2 * agg_precision * agg_recall / (agg_precision + agg_recall)
              if (agg_precision + agg_recall) > 0 else 0)

    # ─── Chat Evaluation ──────────────────────────────────────────────────
    chat_results = []
    chat_skipped = False

    print("\n  Running chat evaluation...")

    for qa in qa_cases:
        pair_id = qa["pair_id"]
        # Look up the doc IDs from delta_cases
        pair_case = next((c for c in delta_cases if c["pair_id"] == pair_id), None)
        if pair_case:
            doc_a_id = pair_case.get("doc_a_id", f"EVAL-{pair_id}-A")
            doc_b_id = pair_case.get("doc_b_id", f"EVAL-{pair_id}-B")
        else:
            doc_a_id = f"EVAL-{pair_id}-A"
            doc_b_id = f"EVAL-{pair_id}-B"

        answer = asyncio.run(_run_chat_question(qa["question"], doc_a_id, doc_b_id))

        if answer.get("skipped"):
            chat_skipped = True
            break

        scores = score_chat(qa, answer)
        chat_results.append({
            "pair_id": pair_id,
            "question": qa["question"],
            "answer": answer.get("answer", "")[:200],
            **scores,
        })

    # Aggregate chat metrics
    if chat_skipped or not chat_results:
        chat_metrics = {
            "correctness": None,
            "groundedness": None,
            "citation_accuracy": None,
            "note": "SKIPPED - OPENROUTER_API_KEY not set or LLM unavailable",
        }
    else:
        n_q = len(chat_results)
        chat_metrics = {
            "correctness": round(sum(1 for r in chat_results if r["correct"]) / n_q * 100, 1),
            "groundedness": round(sum(1 for r in chat_results if r["grounded"]) / n_q * 100, 1),
            "citation_accuracy": round(sum(1 for r in chat_results if r["citation_accurate"]) / n_q * 100, 1),
        }

    # ─── Print Scorecard ──────────────────────────────────────────────────
    print("\n")
    print("=" * 40)
    print("DOCUMENT DELTA EVALUATION")
    print("=" * 40)
    print(f"Dataset: {n_pairs} pairs, {total_expected} expected changes, {len(qa_cases)} chat questions")
    print()
    print("DELTA METRICS")
    print("-------------")
    print(f"Precision: {agg_precision:.2f}")
    print(f"Recall:    {agg_recall:.2f}")
    print(f"F1:        {agg_f1:.2f}")
    print()
    print("CHAT METRICS")
    print("------------")
    if chat_metrics.get("note"):
        print(f"  {chat_metrics['note']}")
    else:
        print(f"Correctness: {chat_metrics['correctness']}%")
        print(f"Groundedness: {chat_metrics['groundedness']}%")
        print(f"Citation Accuracy: {chat_metrics['citation_accuracy']}%")
    print()
    print("FAILURES")
    print("---------")

    if all_missed:
        for m in all_missed[:10]:
            ct = m.get("change_type", "?")
            old = m.get("old_value", "")
            new = m.get("new_value", "")
            pid = m.get("pair_id", "?")
            print(f"  MISSED [{pid}] {ct}: '{old}' → '{new}'")

    if all_false_positives:
        for fp in all_false_positives[:10]:
            ct = fp.get("change_type", "?")
            old = fp.get("old_value", "")
            new = fp.get("new_value", "")
            pid = fp.get("pair_id", "?")
            print(f"  FALSE_POS [{pid}] {ct}: '{old}' → '{new}'")

    if chat_results:
        incorrect = [r for r in chat_results if not r["correct"]]
        for r in incorrect[:5]:
            print(f"  INCORRECT_CHAT [{r['pair_id']}] Q: '{r['question'][:60]}' "
                  f"A: '{r['answer'][:80]}...'")

    if not all_missed and not all_false_positives and not any(
        not r["correct"] for r in chat_results
    ):
        print("  (none)")

    print("=" * 40)

    # ─── Persist Results ──────────────────────────────────────────────────
    results = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "delta_metrics": {
            "precision": round(agg_precision, 4),
            "recall": round(agg_recall, 4),
            "f1": round(agg_f1, 4),
            "total_matched": len(all_matched),
            "total_missed": len(all_missed),
            "total_false_positives": len(all_false_positives),
        },
        "chat_metrics": chat_metrics,
        "failures": {
            "missed": all_missed[:20],
            "false_positives": [
                {"pair_id": fp.get("pair_id"), "change_type": fp.get("change_type"),
                 "old_value": (fp.get("old_value") or "")[:100],
                 "new_value": (fp.get("new_value") or "")[:100]}
                for fp in all_false_positives[:20]
            ],
            "incorrect_chat": [r for r in chat_results if not r.get("correct")][:10],
        },
    }

    _persist_results(results)


if __name__ == "__main__":
    main()
