# Style Reference: One Complete Question Exchange

This is a worked example from Episode 1 (Claude Certified Architect – Foundations). It shows the same question in both output forms. Match this voice, density, and structure.

What to imitate:

- Jordan nicknames the question, reads the stem faithfully, and reads **every** option.
- Maya names the answer in her first sentence, then states the *principle* that decides it.
- Every distractor gets its own treatment, framed as a mistake real teams make — with varied phrasing, never a repeated formula.
- Jordan pushes back once, defending the most tempting wrong answer, so Maya can dismantle it conversationally.
- The exchange ends by naming the concrete mechanism, not just the letter.

---

## Form 1 — Readable script (`.md`)

### Question 1 — The Agent That Skips Verification

**JORDAN:** Production data shows that in **12% of cases**, your agent skips `get_customer` entirely and calls `lookup_order` using only the customer's *stated name* — occasionally leading to misidentified accounts and incorrect refunds. What change would most effectively address this reliability issue?

**A.** Add a programmatic prerequisite that blocks `lookup_order` and `process_refund` calls until `get_customer` has returned a verified customer ID.
**B.** Enhance the system prompt to state that customer verification via `get_customer` is mandatory before any order operations.
**C.** Add few-shot examples showing the agent always calling `get_customer` first, even when customers volunteer order details.
**D.** Implement a routing classifier that analyzes each request and enables only the subset of tools appropriate for that request type.

**MAYA:** The answer is **A** — the programmatic prerequisite. And this question is teaching you maybe the single most important principle on the whole exam: **when compliance must be guaranteed, enforce it in code, not in the prompt.**

**JORDAN:** Why isn't a stern system prompt enough? "Verification is MANDATORY," bold, all caps.

**MAYA:** Because prompt instructions are *probabilistic*. They shift the distribution of behavior; they don't constrain it. B and C — the stronger prompt and the few-shot examples — will probably get you from a 12% failure rate down to, who knows, 2%, 1%. But this is identity verification before issuing refunds. Money is moving. A 1% failure rate on financial operations is not a win, it's an incident report. This is the classic mistake, by the way — teams discover the agent misbehaves, and their reflex is to write a longer prompt. Prompts are for guidance. Hooks and gates are for guarantees.

**JORDAN:** And D? The routing classifier sounds sophisticated.

**MAYA:** D is a well-disguised wrong answer because it's solving a *different problem*. A routing classifier controls which tools are **available** for a request type. But the problem here isn't availability — it's **ordering**. It's calling a legitimate tool at the wrong time, before its prerequisite. People pick D because it sounds like serious engineering. Always ask: does this mechanism actually address the failure I observed?

**JORDAN:** So: hook that blocks the downstream tools until `get_customer` returns a verified ID.

**MAYA:** Exactly. Deterministic business rules live in hooks.

---

## Form 2 — The same exchange in the TTS master (`.tts.txt`)

Note the transformations: one turn per line, options folded into the host's turn as "Option A: …", `get_customer` → "get-customer", "ID" → "I-D", "12%" → "twelve percent", no markdown, no emphasis markers.

```
JORDAN: Question one. I'm calling this one: the agent that skips verification. Production data shows that in twelve percent of cases, your agent skips get-customer entirely, and calls lookup-order using only the customer's stated name — occasionally leading to misidentified accounts and incorrect refunds. What change would most effectively address this reliability issue? Option A: add a programmatic prerequisite that blocks lookup-order and process-refund calls until get-customer has returned a verified customer I-D. Option B: enhance the system prompt to state that customer verification via get-customer is mandatory before any order operations. Option C: add few-shot examples showing the agent always calling get-customer first, even when customers volunteer order details. Option D: implement a routing classifier that analyzes each request and enables only the subset of tools appropriate for that request type.

MAYA: The answer is A — the programmatic prerequisite. And this question is teaching you maybe the single most important principle on the whole exam: when compliance must be guaranteed, enforce it in code, not in the prompt.

JORDAN: Why isn't a stern system prompt enough? Verification is mandatory — bold, all caps.

MAYA: Because prompt instructions are probabilistic. They shift the distribution of behavior; they don't constrain it. B and C — the stronger prompt and the few-shot examples — will probably get you from a twelve percent failure rate down to, who knows, two percent, one percent. But this is identity verification before issuing refunds. Money is moving. A one percent failure rate on financial operations is not a win, it's an incident report. This is the classic mistake, by the way — teams discover the agent misbehaves, and their reflex is to write a longer prompt. Prompts are for guidance. Hooks and gates are for guarantees.

JORDAN: And D? The routing classifier sounds sophisticated.

MAYA: D is a well-disguised wrong answer, because it's solving a different problem. A routing classifier controls which tools are available for a request type. But the problem here isn't availability — it's ordering. It's calling a legitimate tool at the wrong time, before its prerequisite. People pick D because it sounds like serious engineering. Always ask: does this mechanism actually address the failure I observed?

JORDAN: So: a hook that blocks the downstream tools until get-customer returns a verified I-D.

MAYA: Exactly. Deterministic business rules live in hooks.
```
