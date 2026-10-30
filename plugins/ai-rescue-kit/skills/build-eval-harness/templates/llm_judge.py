"""LLM-as-judge grader: one criterion per call, structured verdict.

Use it only for open-ended answers that a string or number check can't grade. Each ``check`` is a
single natural-language criterion, e.g. "Response mentions that prices can be looked up".

The verdict comes back as schema-constrained JSON with an enum, so there is no free-text parsing and
no sampling parameters to set. Verify the exact parameter names for structured outputs against the
current API docs (or the ``claude-api`` skill) before relying on them: they have changed between
SDK versions.

Setup:
    from llm_judge import make_llm_judge
    GRADER_REGISTRY["llm_judge"] = make_llm_judge(client, model)

``client`` is an ``anthropic.Anthropic`` instance. The judge model is your choice; a small, fast model
is usually enough for one narrow criterion. Spot-check the judge against a few answers you grade by
hand before you trust it.
"""

import json

JUDGE_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
            "reason": {"type": "string", "description": "One sentence."},
        },
        "required": ["verdict", "reason"],
        "additionalProperties": False,
    },
}

JUDGE_SYSTEM = (
    "You grade one criterion about an AI assistant's answer. Judge only that criterion, not the "
    "answer overall. Return PASS only if the criterion is clearly met by the answer text."
)


def build_judge_prompt(query, answer, criterion):
    return (
        f"User query:\n{query}\n\n"
        f"Assistant answer:\n{answer}\n\n"
        f"Criterion:\n{criterion}"
    )


def make_llm_judge(client, model, max_tokens=300):
    """Return a grader function bound to a client and judge model."""

    def grade_llm_judge(result, check, context=None):
        query = (context or {}).get("query", "")
        prompt = build_judge_prompt(query, result.get("final_text") or "", check)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": JUDGE_SCHEMA},
        )
        text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        data = json.loads(text)
        return {
            "score": 1 if data["verdict"] == "PASS" else 0,
            "reason": data["reason"],
        }

    return grade_llm_judge
