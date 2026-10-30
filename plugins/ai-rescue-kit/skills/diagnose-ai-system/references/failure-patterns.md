# Failure patterns: a starting list of hypotheses

Use this to seed hypotheses, not to replace looking. Each entry gives the symptom that points to it, where to look, and the kind of fix that usually works. Treat every one as a hypothesis until you have quoted a line.

## System and agent structure

### Routing or classification failure
- **Symptom:** the wrong specialist handles a request, or only part of what the user asked for is handled. The same input is routed differently from run to run.
- **Look at:** the router's prompt and its output format (does it allow one label, or several?); the routing field in each trace; how often the decision varies across runs.
- **Typical fix:** make the router's instructions and output format match what real requests look like, including requests with more than one part. Re-measure the routing decisions, not just the final answer.

### Tool descriptions too vague to use reliably
- **Symptom:** the model calls the wrong tool, passes badly formed arguments, or doesn't call a tool it should.
- **Look at:** each tool's `description` and parameter descriptions. If they only repeat the name ("calculator", "operator"), the model is guessing.
- **Typical fix:** say what the tool does, when to use it and when not to, the format of each argument with an example, and what it returns or how it fails.

### Missing or wrong escalation path
- **Symptom:** the system answers confidently when it should hand off to a person, or loops, or gives up silently.
- **Look at:** whether any tool or instruction lets the agent say "I can't resolve this", and what the prompt tells it to do when it can't.
- **Typical fix:** add an explicit escalation tool or instruction, and a check that the agent uses it when its own steps failed.

### A sub-agent claims resolution it did not achieve
- **Symptom:** the final message says the problem is fixed, and the trace shows the fix step failed, was skipped, or was never possible.
- **Look at:** the sub-agent's final-message instructions; tool results that returned errors; whether the coordinator trusts the sub-agent's summary without checking.
- **Typical fix:** require the sub-agent to report what it did and what the tool returned; make the coordinator check results before telling the user anything is resolved.

### Context does not reach the model that needs it
- **Symptom:** a later step contradicts or ignores something an earlier step established; names, ids or amounts are missing or wrong.
- **Look at:** the exact request sent at the failing step. Is the earlier information in it?
- **Typical fix:** pass the needed context explicitly, in the request that needs it.

### Cache placement breaks shared prefixes
- **Symptom:** high cost or latency on a workload that repeats a large unchanging prompt; `cache_read_input_tokens` stays at zero.
- **Look at:** where volatile content (timestamps, ids, the user's text) sits relative to the stable content. Any change in the prefix invalidates what follows it.
- **Typical fix:** stable content first and marked for caching, volatile content after. See the `optimize-inference` skill.

## Prompt design

### Several tasks in one prompt interfere with each other
- **Symptom:** a field is wrong in a way that matches the tone or content of another part of the output (for example, a classification is inflated when the same prompt also writes a sympathetic reply).
- **Look at:** how many different jobs one prompt asks for (classify, extract, draft). Check failures for a pattern that links one output to another.
- **Typical fix:** prompt chaining (one focused step per job), weighed against the added latency of each call.

### "Include all fields" causes invented values
- **Symptom:** fields filled with plausible but made-up values when the input doesn't contain them (product names, error codes, owners, dates).
- **Look at:** instructions such as "always include every field". The model reads "include" as "fill in".
- **Typical fix:** say explicitly that a missing value is `null` or "not stated", and give an example of an input with missing fields and its correct output.

### Urgent or emotional tone inflates priority or severity
- **Symptom:** angry or urgent wording produces a high-severity label even when the content is minor.
- **Look at:** the definition of each level. If it doesn't say to judge content, not tone, the model matches urgency words to high levels.
- **Typical fix:** tell the model to ignore tone and judge content; add examples of urgent-sounding minor requests with their correct label.

### Feature requests or questions read as defects
- **Symptom:** a request for new behaviour is classified as a bug or incident.
- **Look at:** whether the categories include a clear definition and an example of each, and whether the boundary cases are shown.
- **Typical fix:** add definitions and boundary examples (few-shot), and re-check the easy cases for regressions.

## Always test

### The model really is not capable enough
- **Symptom:** the failure persists after the structure is sound.
- **How to test:** run the same eval on a larger model, nothing else changed (step 5 of the skill). If the rate does not move, or moves less than the cost increase justifies, the cause is elsewhere.
