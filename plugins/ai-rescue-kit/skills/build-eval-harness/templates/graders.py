"""Deterministic graders and the grader registry.

A grader is a function ``grader(result, check, context=None) -> {"score": 0|1, "reason": str}``.

``result`` is a parsed transcript:
    {"final_text": str,
     "tool_calls": [{"name": str, "arguments": dict, "result": str | None}, ...]}

``check`` is one entry from a task's ``checks`` list; its shape depends on the grader.
``context`` carries the task: {"query": ..., "task_id": ..., "model": ...}.

Add a grader with one function and one registry entry. Standard library only.
"""

import re


def grade_response_contains(result, check, context=None):
    """Final text contains a string, case-insensitive. check: "49.99"."""
    text = (result.get("final_text") or "").lower()
    if str(check).lower() in text:
        return {"score": 1, "reason": f"found {check!r} in response"}
    return {"score": 0, "reason": f"{check!r} not found in response: {text[:200]!r}"}


def grade_response_numeric(result, check, context=None):
    """Final text contains a number within a tolerance.

    check: 49.99  (tolerance 0.01)  or  {"value": 49.99, "tolerance": 0.05}
    """
    if isinstance(check, (int, float)):
        value, tolerance = float(check), 0.01
    else:
        value = float(check["value"])
        tolerance = float(check.get("tolerance", 0.01))

    numbers = re.findall(r"-?\d[\d,]*\.?\d*", result.get("final_text") or "")
    for raw in numbers:
        try:
            number = float(raw.replace(",", "").rstrip("."))
        except ValueError:
            continue
        if abs(number - value) <= tolerance:
            return {"score": 1, "reason": f"found {number} (expected {value} +/- {tolerance})"}
    return {"score": 0, "reason": f"expected {value} +/- {tolerance}, found {numbers[:10]}"}


def grade_tool_use(result, check, context=None):
    """The agent called a tool, optionally with specific arguments.

    check: {"tool_name": "lookup"}  or  {"tool_name": "lookup", "arguments": {"item": "x"}}

    This verifies that the answer was grounded in a tool, not a fixed call order. Only pin
    ``arguments`` when the argument value is the thing under test. Only the keys you list are
    compared; strings match case-insensitively.
    """
    wanted = check["tool_name"]
    expected = check.get("arguments")
    calls = result.get("tool_calls") or []

    for call in calls:
        if call.get("name") != wanted:
            continue
        if not expected:
            return {"score": 1, "reason": f"tool {wanted!r} was called"}
        actual = call.get("arguments") or {}
        if all(_same(actual.get(key), value) for key, value in expected.items()):
            return {"score": 1, "reason": f"tool {wanted!r} called with {expected}"}

    seen = [{"name": c.get("name"), "args": c.get("arguments")} for c in calls]
    if expected:
        return {"score": 0, "reason": f"{wanted!r} not called with {expected}; calls were {seen}"}
    return {"score": 0, "reason": f"{wanted!r} never called; calls were {[c['name'] for c in seen]}"}


def _same(actual, expected):
    if isinstance(expected, str) and isinstance(actual, str):
        return actual.strip().lower() == expected.strip().lower()
    return actual == expected


GRADER_REGISTRY = {
    "response_contains": grade_response_contains,
    "response_numeric": grade_response_numeric,
    "tool_use": grade_tool_use,
}
