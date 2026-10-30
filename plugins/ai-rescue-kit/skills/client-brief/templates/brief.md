# Client brief: {client} {system} pilot

*One page. Every number names its run. A line in [GAP: …] means no run measures it yet.*

**Client and pilot**
{Who the client is, what the AI system does, how long it has been live, and what the problem looks like from their side. One or two sentences.}

**What's actually breaking it**
*(Plain language. Name the system around the model, not the model. Explain any technical word in a few everyday words.)*

{What the system does wrong, in terms the client's team would recognise, with one concrete example from their own cases.}

**The fix**
*(What we changed and where, without jargon.)*

{Change 1: what it does differently now. Change 2: …}

**Proof**
*(Before → after on the same measure. Same tasks, same number of runs.)*

| | Before | After | Run |
|---|---|---|---|
| Success rate on the cases we tuned on | {x% (run: baseline)} | {y% (run: fix-n)} | |
| Success rate on cases we hadn't seen | n/a | {z% (run: holdout-final)} | |
| Cost per {unit} | ${…} (run: baseline) | ${…} (run: fix-n) | |

{One line on what the numbers mean for the client. If hold-out is missing: [GAP: fix not yet shown on unseen cases; run the held-out set once.]}

**What it would take**
*(Rough scope, and the constraint to hit, such as staying within the current cost per {unit}.)*

{Scope, who does what, and what stays the same.}

**The objection we'll get: "Why not just use a better model?"**
*(Answer with our own test: same cases, bigger model, nothing else changed.)*

{Bigger model: x% (run: bigger-model) at $… per {unit}. Fixed system on the current model: y% (run: fix-n) at $… per {unit}. Therefore …}
{If no such run exists: [GAP: no bigger-model run in runs.jsonl; run the baseline cases on a larger model, nothing else changed.]}

**Prevention: three questions for every new prompt**
1. Does this prompt ask the model to do more than one job at once? If so, could one job's output distort another's?
2. What should the model do when the information it needs is missing or the request is unclear, and does the prompt say so, with an example?
3. Do we have a set of real cases, including the hardest, that we run several times before and after every change, and a set we keep aside to check we haven't just tuned to the ones we looked at?

**Sources:** `rescue-notes.md`; runs: {list of labels used}.
