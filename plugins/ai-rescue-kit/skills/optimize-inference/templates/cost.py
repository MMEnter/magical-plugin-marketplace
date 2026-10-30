"""Cache-aware cost for Claude API calls. Standard library only.

    from cost import calculate_cost
    usd = calculate_cost("claude-sonnet-5-5", response.usage)               # one call
    usd = calculate_cost("claude-sonnet-5-5", response.usage, batch=True)   # Batch API: 50% off

A cost function that prices only input and output misprices any cached workload. This one uses all
four terms: plain input, output, cache writes, cache reads. Rates are read from ``pricing.md``
(never hard-coded here) so there is one place to update and one "verified on" date. By default it looks for
``pricing.md`` next to this file, then in ``../references/``; pass ``pricing_path`` to override.

``usage`` may be an Anthropic ``Usage`` object or a dict with ``input_tokens``, ``output_tokens``,
``cache_creation_input_tokens`` and ``cache_read_input_tokens``. Missing or None fields count as 0.
If your calls use the 1-hour cache lifetime, pass ``cache_ttl="1h"``.
"""

import os
import re

BATCH_MULTIPLIER = 0.5  # Batch API: 50% off all token charges (check pricing.md)
LONG_PROMPT_TOKENS = 100_000

_ROW = re.compile(r"^\|\s*`(?P<model>[^`]+)`\s*\|(?P<cells>.*)\|\s*$")
_cache = {}


def _default_path():
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, "pricing.md"),
                      os.path.join(here, "..", "references", "pricing.md")):
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("pricing.md not found next to cost.py or in ../references/")


def load_pricing(pricing_path=None):
    """Parse the pricing table into {model_id: {input, cache_write_5m, cache_write_1h, cache_read, output}}."""
    path = pricing_path or _default_path()
    if path in _cache:
        return _cache[path]
    table = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = _ROW.match(line.strip())
            if not m:
                continue
            cells = [c.strip() for c in m.group("cells").split("|")]
            try:
                numbers = [float(c) for c in cells[:5]]
            except ValueError:
                continue
            table[m.group("model")] = dict(zip(
                ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output"), numbers))
    if not table:
        raise ValueError(f"no pricing rows found in {path}")
    _cache[path] = table
    return table


def _get(usage, name):
    value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
    return value or 0


def calculate_cost(model, usage, batch=False, cache_ttl="5m", pricing_path=None):
    """Fully loaded dollars for one call, including cache writes and reads."""
    table = load_pricing(pricing_path)
    uncached = _get(usage, "input_tokens")
    writes = _get(usage, "cache_creation_input_tokens")
    reads = _get(usage, "cache_read_input_tokens")
    output = _get(usage, "output_tokens")

    key = model
    if f"{model}@>100k" in table and (uncached + writes + reads) > LONG_PROMPT_TOKENS:
        key = f"{model}@>100k"
    if key not in table:
        raise KeyError(f"{model!r} is not in pricing.md; add a row from the pricing page (do not guess)")
    p = table[key]
    write_rate = p["cache_write_1h"] if cache_ttl == "1h" else p["cache_write_5m"]

    dollars = (uncached * p["input"] + writes * write_rate + reads * p["cache_read"]
               + output * p["output"]) / 1e6
    return dollars * (BATCH_MULTIPLIER if batch else 1.0)


def summarize_usage(model, usages, batch=False):
    """Total cost and cache hit share across several calls (a list of usage objects)."""
    total = sum(calculate_cost(model, u, batch=batch) for u in usages)
    reads = sum(_get(u, "cache_read_input_tokens") for u in usages)
    all_in = sum(_get(u, "input_tokens") + _get(u, "cache_creation_input_tokens")
                 + _get(u, "cache_read_input_tokens") for u in usages)
    return {"cost_usd": total, "calls": len(usages),
            "cache_read_share_of_input": (reads / all_in) if all_in else 0.0}


if __name__ == "__main__":  # quick check: python cost.py
    demo = {"input_tokens": 400, "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 5000, "output_tokens": 300}
    for name in ("claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"):
        print(f"{name:20s} ${calculate_cost(name, demo):.6f}   batch ${calculate_cost(name, demo, batch=True):.6f}")
