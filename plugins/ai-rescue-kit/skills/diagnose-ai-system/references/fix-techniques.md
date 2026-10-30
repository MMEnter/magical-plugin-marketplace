# Fix techniques

Pick the technique from the diagnosis, not from habit. For each: what it is, which failure it fits, and when not to use it. Whatever you pick, change one thing at a time and re-measure.

## Constraint sharpening
**What it is:** replace vague instructions with explicit rules, including what to do when information is missing or a case is ambiguous.
**Fits:** invented values, tone inflating a label, the model doing something you didn't forbid, unclear definitions of categories.
**Not when:** the prompt already says the right thing and the model still fails; adding more rules to a long prompt makes rules compete.

## Few-shot examples
**What it is:** show two or three inputs with their correct outputs, including boundary cases and cases where the right answer is "nothing" or "null".
**Fits:** boundary cases between categories, output format drift, the model needing to see what "not stated" looks like.
**Not when:** the examples are close copies of your test cases (that tunes to the test), or when they would be longer than the task itself. Use inputs that differ from the evaluation set.

## Prompt chaining
**What it is:** split a prompt that does several jobs into steps with one job each; each step has its own prompt.
**Fits:** task interference, where one output visibly contaminates another.
**Cost:** every extra call adds latency and cost. With a response-time budget, divide it across the steps (three sequential calls in 5 seconds leave about 1.5 s each). Collapse any step that doesn't earn its time.
**Not when:** the jobs don't interfere; then you are paying for calls you don't need.

## Meta-prompting
**What it is:** give Claude the prompt and two or three failing examples and ask what in the prompt could cause these outputs: which instructions are ambiguous, conflicting or missing.
**Fits:** you can't see why the prompt fails; you want a list of candidate causes.
**Treat the answer as a lead, not a finding.** You still need to quote the line and measure the fix. Do not describe a fix as "Claude fixed it": the diagnosis and the decision are the team's.

## A/B comparison
**What it is:** run two prompt variants over the same eval and compare category by category, with enough runs per task that the difference is bigger than the run-to-run noise.
**Fits:** you have two plausible framings and no way to choose between them by reading.
**Not when:** you have one hypothesis and haven't tested it yet; test that first.

## Automatic variant search
**What it is:** a loop that generates prompt variants (with meta-prompting), evaluates each, and keeps the best. A manual version: three variants of the hardest instruction, evaluate all, keep the winner.
**Fits:** you have plateaued, and the remaining failures aren't explained by anything you can point to.
**Not when:** you don't yet understand the failures. Search finds a prompt that scores well on your eval; it can't tell you why. Always check the winner on the held-out set.

## Fixes outside the prompt
Not every failure is a prompt failure. Fix tool definitions (clear descriptions, argument formats), routing (labels that match real requests), the data passed between steps, validation of model output in code, and escalation paths. Prefer a code check over a prompt instruction where a rule can be checked deterministically.
