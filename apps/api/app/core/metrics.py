"""Minimal in-process metrics in Prometheus text format (no extra dependency).

Counters and one latency histogram, labelled by route template (never by raw path,
address, workspace or anything user-supplied), so label cardinality stays bounded.
Values are per process and reset on restart.
"""
from __future__ import annotations

import threading
from collections import defaultdict

LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
_ALLOWED = {
    "trace_http_requests_total": "HTTP requests by method, route template and status.",
    "trace_analyses_total": "Wallet analyses by outcome.",
    "trace_provider_failures_total": "External provider failures by provider and kind.",
    "trace_memory_recall_total": "Memory recall during analysis by status.",
    "trace_history_saves_total": "Investigation history saves by outcome.",
}


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
        self._hist: dict[str, list[float]] = {}
        self._hist_sum: dict[str, float] = defaultdict(float)
        self._hist_count: dict[str, int] = defaultdict(int)

    def inc(self, name: str, **labels: str) -> None:
        if name not in _ALLOWED:
            raise KeyError(name)
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            self._counters[name][key] += 1

    def observe_latency(self, route: str, seconds: float) -> None:
        with self._lock:
            buckets = self._hist.setdefault(route, [0.0] * len(LATENCY_BUCKETS))
            for i, bound in enumerate(LATENCY_BUCKETS):
                if seconds <= bound:
                    buckets[i] += 1
            self._hist_sum[route] += seconds
            self._hist_count[route] += 1

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._hist.clear()
            self._hist_sum.clear()
            self._hist_count.clear()

    def value(self, name: str, **labels: str) -> float:
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        return self._counters.get(name, {}).get(key, 0.0)

    @staticmethod
    def _labels(pairs) -> str:
        if not pairs:
            return ""
        inner = ",".join(f'{k}="{v.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"' for k, v in pairs)
        return "{" + inner + "}"

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for name, help_text in _ALLOWED.items():
                lines += [f"# HELP {name} {help_text}", f"# TYPE {name} counter"]
                for key, value in sorted(self._counters.get(name, {}).items()):
                    lines.append(f"{name}{self._labels(key)} {value:g}")
            name = "trace_http_request_duration_seconds"
            lines += [f"# HELP {name} Request latency by route template.", f"# TYPE {name} histogram"]
            for route in sorted(self._hist):
                for bound, count in zip(LATENCY_BUCKETS, self._hist[route]):
                    lines.append(f"{name}_bucket{self._labels((('le', f'{bound:g}'), ('route', route)))} {count:g}")
                lines.append(f"{name}_bucket{self._labels((('le', '+Inf'), ('route', route)))} {self._hist_count[route]}")
                lines.append(f"{name}_sum{self._labels((('route', route),))} {self._hist_sum[route]:.6f}")
                lines.append(f"{name}_count{self._labels((('route', route),))} {self._hist_count[route]}")
        return "\n".join(lines) + "\n"


metrics = Metrics()
