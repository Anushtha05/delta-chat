"""In-process metrics recorder — counters and histograms, no external deps.

Tracks latencies, counts, and token usage. Exposes a JSON snapshot via GET /api/metrics.
"""

import statistics
import threading
import time
from collections import defaultdict


class MetricsRecorder:
    """Thread-safe in-process metrics with counters and latency histograms."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter."""
        with self._lock:
            self._counters[name] += value

    def record_latency(self, name: str, duration_ms: float) -> None:
        """Record a latency sample (in milliseconds)."""
        with self._lock:
            self._histograms[name].append(duration_ms)

    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of all metrics."""
        with self._lock:
            result = {
                "counters": dict(self._counters),
                "latencies": {},
            }
            for name, values in self._histograms.items():
                if not values:
                    continue
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                result["latencies"][name] = {
                    "count": n,
                    "min_ms": round(sorted_vals[0], 2),
                    "max_ms": round(sorted_vals[-1], 2),
                    "p50_ms": round(sorted_vals[n // 2], 2),
                    "p95_ms": round(sorted_vals[int(n * 0.95)], 2) if n > 1 else round(sorted_vals[0], 2),
                    "mean_ms": round(statistics.mean(sorted_vals), 2),
                }
            return result


# Module-level singleton
metrics = MetricsRecorder()
