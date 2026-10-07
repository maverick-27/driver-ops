"""Performance monitoring and metrics collection."""

import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, asdict
import json

@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    timestamp: str
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    query_length: int
    documents_retrieved: int
    cached: bool

    def to_dict(self):
        return asdict(self)

class MetricsCollector:
    """Collect and aggregate performance metrics."""

    def __init__(self, max_history: int = 1000):
        self.metrics: list[RequestMetrics] = []
        self.max_history = max_history

    def record(self, metric: RequestMetrics):
        """Record a metric."""
        self.metrics.append(metric)
        # Keep only recent metrics
        if len(self.metrics) > self.max_history:
            self.metrics = self.metrics[-self.max_history:]

    def get_stats(self, minutes: int = 5) -> dict:
        """Get performance stats for the last N minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        recent = [m for m in self.metrics if datetime.fromisoformat(m.timestamp) > cutoff]

        if not recent:
            return {"requests": 0, "avg_time_ms": 0, "p95_time_ms": 0, "p99_time_ms": 0}

        times = sorted([m.response_time_ms for m in recent])
        n = len(times)

        return {
            "requests": n,
            "avg_time_ms": sum(times) / n,
            "p50_time_ms": times[n // 2],
            "p95_time_ms": times[int(n * 0.95)],
            "p99_time_ms": times[int(n * 0.99)],
            "min_time_ms": times[0],
            "max_time_ms": times[-1],
            "cached_ratio": sum(1 for m in recent if m.cached) / n if n > 0 else 0,
        }

    def get_top_queries(self, limit: int = 10) -> list[dict]:
        """Get slowest queries."""
        sorted_metrics = sorted(self.metrics, key=lambda m: m.response_time_ms, reverse=True)
        return [
            {
                "response_time_ms": m.response_time_ms,
                "endpoint": m.endpoint,
                "status": m.status_code,
                "timestamp": m.timestamp,
            }
            for m in sorted_metrics[:limit]
        ]

# Global metrics collector
metrics_collector = MetricsCollector()
