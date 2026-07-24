"""Quick script to verify ground truth alignment by running ingestion + comparison."""
import os, json, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
os.environ['TESTING'] = 'true'

from pathlib import Path
from src.ingest.registry import registry
from src.delta.engine import compare_documents
from eval.metrics import score_delta

samples = Path(__file__).resolve().parent.parent / 'data' / 'samples'

with open(Path(__file__).resolve().parent / 'datasets' / 'delta_cases.json') as f:
    cases = json.load(f)

for case in cases:
    pair_id = case['pair_id']
    doc_a = registry.ingest_file(str(samples / case['doc_a_path']), f'VERIFY-{pair_id}-A', 'A')
    doc_b = registry.ingest_file(str(samples / case['doc_b_path']), f'VERIFY-{pair_id}-B', 'B')
    records = compare_documents(doc_a, doc_b)
    result = score_delta(case['expected_changes'], records)
    n_exp = len(case['expected_changes'])
    print(f"{pair_id}: P={result['precision']:.3f} R={result['recall']:.3f} F1={result['f1']:.3f} "
          f"(expected={n_exp}, detected={len(records)}, matched={len(result['matched'])}, "
          f"missed={len(result['missed'])}, FP={len(result['false_positives'])})")
    for m in result['missed']:
        ct = m.get('change_type', '?')
        old = m.get('old_value', '')
        new = m.get('new_value', '')
        print(f"  MISSED: {ct}: {old!r} -> {new!r}")
    for fp in result['false_positives'][:3]:
        ct = fp.get('change_type', '?')
        old = fp.get('old_value', '')
        new = fp.get('new_value', '')
        print(f"  FP: {ct}: {old!r} -> {new!r}")
