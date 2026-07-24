"""Evaluation scoring functions for delta detection and chat correctness.

score_delta: precision/recall/F1 on structured delta outputs
score_chat: correctness/groundedness/citation accuracy on LLM answers
"""

from rapidfuzz import fuzz

from src.delta.model import DeltaRecord
from src.delta.normalize import normalize


def _values_match(expected: str | None, actual: str | None, threshold: float = 75.0) -> bool:
    """Check if expected and actual values match using normalized fuzzy comparison.

    Uses normalize() to strip formatting differences, then rapidfuzz ratio
    with a configurable threshold. None values only match other None values.
    """
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False

    norm_exp = normalize(expected)
    norm_act = normalize(actual)

    # Exact normalized match
    if norm_exp == norm_act:
        return True

    # Fuzzy match with threshold
    ratio = fuzz.ratio(norm_exp, norm_act)
    return ratio >= threshold


def score_delta(expected: list[dict], actual: list[DeltaRecord]) -> dict:
    """Score delta detection: precision, recall, F1.

    Matches expected changes against actual DeltaRecords by:
    (change_type, old_value, new_value) using fuzzy normalized matching.

    Returns:
        {
            "precision": float,  # matched / total_actual (relevant ones)
            "recall": float,     # matched / total_expected
            "f1": float,
            "matched": list[dict],       # successfully matched changes
            "false_positives": list[dict], # actual changes not in expected
            "missed": list[dict],         # expected changes not found in actual
        }
    """
    # Convert actual records to comparable dicts
    actual_dicts = []
    for r in actual:
        actual_dicts.append({
            "change_type": r.change_type,
            "element_type": r.element_type,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "change_id": r.change_id,
        })

    matched: list[dict] = []
    matched_actual_ids: set[int] = set()  # indices into actual_dicts

    # For each expected change, find the best matching actual change
    for exp in expected:
        best_idx = -1
        best_score = 0.0

        for i, act in enumerate(actual_dicts):
            if i in matched_actual_ids:
                continue

            # Must match on change_type
            if exp["change_type"] != act["change_type"]:
                continue

            # Score old_value match
            old_match = _values_match(exp.get("old_value"), act.get("old_value"))
            new_match = _values_match(exp.get("new_value"), act.get("new_value"))

            if old_match and new_match:
                # Both match — perfect
                score = 2.0
            elif old_match or new_match:
                # One matches — partial (still counts as a match)
                score = 1.0
            else:
                score = 0.0

            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx >= 0 and best_score >= 1.0:
            matched.append({
                "expected": exp,
                "actual": actual_dicts[best_idx],
                "score": best_score,
            })
            matched_actual_ids.add(best_idx)

    # Identify missed and false positives
    missed = [exp for i, exp in enumerate(expected)
              if not any(m["expected"] is exp for m in matched)]

    # False positives: actual changes that don't match ANY expected
    # But we only count meaningful ones (not trivial "Rev: A" → "Rev: B" type changes)
    false_positives = []
    for i, act in enumerate(actual_dicts):
        if i not in matched_actual_ids:
            # Filter out trivially uninteresting false positives (like "Rev:" changes)
            # to keep the failure report manageable
            val = act.get("old_value") or act.get("new_value") or ""
            if len(val) > 2:  # Skip single-char noise
                false_positives.append(act)

    # Calculate metrics
    n_matched = len(matched)
    n_expected = len(expected)
    n_actual_relevant = n_matched + len(false_positives)

    precision = n_matched / n_actual_relevant if n_actual_relevant > 0 else 0.0
    recall = n_matched / n_expected if n_expected > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "matched": matched,
        "false_positives": false_positives,
        "missed": missed,
    }


def score_chat(qa_case: dict, chat_answer: dict) -> dict:
    """Score a chat answer against ground truth.

    Args:
        qa_case: dict with "expected_answer_contains" and "expected_citation_sources"
        chat_answer: dict with "answer", "citations", "chunk_ids"

    Returns:
        {
            "correct": bool,           # all keywords present in answer
            "grounded": bool,          # citations non-empty
            "citation_accurate": bool, # citation sources overlap with expected
        }
    """
    answer_text = (chat_answer.get("answer") or "").lower()
    expected_keywords = qa_case.get("expected_answer_contains", [])
    expected_sources = set(qa_case.get("expected_citation_sources", []))

    # Correctness: all expected keywords must appear in the answer
    correct = all(kw.lower() in answer_text for kw in expected_keywords)

    # Groundedness: citations list is non-empty
    citations = chat_answer.get("citations", [])
    chunk_ids = chat_answer.get("chunk_ids", [])
    grounded = len(citations) > 0 or len(chunk_ids) > 0

    # Citation accuracy: at least one citation source overlaps with expected
    citation_sources_found: set[str] = set()
    for cit in citations:
        cit_upper = cit.upper()
        if "PID_A" in cit_upper:
            citation_sources_found.add("PID_A")
        if "PID_B" in cit_upper:
            citation_sources_found.add("PID_B")
        if "DELTA" in cit_upper:
            citation_sources_found.add("DELTA_REPORT")

    citation_accurate = len(citation_sources_found & expected_sources) > 0 if expected_sources else True

    return {
        "correct": correct,
        "grounded": grounded,
        "citation_accurate": citation_accurate,
    }
