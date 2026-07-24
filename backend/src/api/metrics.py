"""Metrics API endpoint — JSON snapshot of aggregated metrics since startup."""

from fastapi import APIRouter

from src.observability.metrics import metrics

router = APIRouter(tags=["observability"])


@router.get("/api/metrics")
def get_metrics():
    """Return a JSON snapshot of counters and latency histograms."""
    return metrics.snapshot()
