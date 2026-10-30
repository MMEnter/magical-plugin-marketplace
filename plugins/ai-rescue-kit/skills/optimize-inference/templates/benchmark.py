"""Streaming benchmark helper: TTFT, TTC, OTPS, cost, cache use. Standard library plus the Anthropic SDK.

    from benchmark import measure_call, BenchmarkSuite
    result = measure_call(client, model="...", messages=[...], system=..., max_tokens=300, name="v0")
    suite.add(result); print(suite.summary())

TTFT (time to first token) is stamped at the first content block of the stream. It is the number the user
feels. TTC (time to completion) is total duration; it matters for cost and throughput. OTPS (output tokens
per second) is measured over generation time only (TTC minus TTFT), because time before the first token is
waiting, not generating.

``client`` is an ``anthropic.Anthropic`` instance built by the project's own setup. Extra keyword arguments
(tools, output_config, ...) are passed straight to ``client.messages.stream``: confirm their names against
the current API docs or the ``claude-api`` skill.
"""

import statistics
import time
from dataclasses import dataclass, field
from typing import List, Optional

from cost import calculate_cost


@dataclass
class BenchmarkResult:
    name: str
    model: str
    ttft: float
    total_time: float
    input_tokens: int
    output_tokens: int
    otps: Optional[float] = None
    cost: Optional[float] = None
    cache_read: int = 0
    cache_write: int = 0
    message: object = None


@dataclass
class BenchmarkSuite:
    results: List[BenchmarkResult] = field(default_factory=list)

    def add(self, result):
        self.results.append(result)

    def clear(self):
        self.results = []

    def summary(self):
        """One row per test name: medians, so a single slow call doesn't dominate."""
        groups = {}
        for r in self.results:
            groups.setdefault(r.name, []).append(r)
        header = f"{'test':<24}{'runs':>5}{'TTFT ms':>9}{'TTC ms':>9}{'OTPS':>8}{'$ / call':>11}{'cache rd':>10}"
        lines = [header, "-" * len(header)]
        for name, g in groups.items():
            lines.append(
                f"{name:<24}{len(g):>5}"
                f"{statistics.median(r.ttft for r in g) * 1000:>9.0f}"
                f"{statistics.median(r.total_time for r in g) * 1000:>9.0f}"
                f"{statistics.median(r.otps or 0 for r in g):>8.1f}"
                f"{statistics.mean(r.cost or 0 for r in g):>11.5f}"
                f"{statistics.median(r.cache_read for r in g):>10.0f}")
        return "\n".join(lines)


def compute_otps(ttft, total_time, output_tokens):
    """Output tokens per second over generation time only."""
    return output_tokens / max(total_time - ttft, 1e-9)


def stream_request(client, model, messages, max_tokens=1024, system=None, **kwargs):
    """Stream one request. Returns (ttft_seconds, total_seconds, final_message)."""
    params = dict(model=model, max_tokens=max_tokens, messages=messages, **kwargs)
    if system is not None:
        params["system"] = system
    ttft = None
    start = time.perf_counter()
    with client.messages.stream(**params) as stream:
        for event in stream:
            if ttft is None and event.type == "content_block_start":
                ttft = time.perf_counter() - start
        message = stream.get_final_message()
    total = time.perf_counter() - start
    return (ttft if ttft is not None else total), total, message


def measure_call(client, model, messages, name, max_tokens=1024, system=None, batch=False, **kwargs):
    """One measured streaming call as a BenchmarkResult, priced with all four cost terms."""
    ttft, total, message = stream_request(client, model, messages, max_tokens, system, **kwargs)
    usage = message.usage
    return BenchmarkResult(
        name=name, model=model, ttft=ttft, total_time=total,
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        otps=compute_otps(ttft, total, usage.output_tokens),
        cost=calculate_cost(model, usage, batch=batch),
        cache_read=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_write=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        message=message,
    )
