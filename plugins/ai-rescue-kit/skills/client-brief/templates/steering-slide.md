# {Engagement}: before / after

*Every figure comes from a named run or a stated assumption. Leave a gap rather than fill it by guesswork.*

| Metric | Before | After | Change | Source |
|---|---|---|---|---|
| Accuracy (audited fields) | {x% } | {y%} | {gate held / not held} | runs: {baseline}, {final} |
| Typical response time (p50) | {x s} | {y s} | {n× faster} | runs: {baseline}, {final} |
| Cost per {unit} (measured) | ${…} | ${…} | {n× cheaper} | runs: {baseline}, {final} |
| Annual cost at stated volume | ${…} | ${…} | ${… saved} | computed from assumptions below |
| Margin per {unit} | {x%} | {y%} | | computed from assumptions below |
| Meets response-time commitment ({target}) | {yes/no} | {yes/no} | | run: {final} |

## Assumptions (these feed the computed rows)

| Assumption | Value | Where it came from |
|---|---|---|
| Volume (units per year) | {…} | {client / contract} |
| Scale factor from test cases to production units | {…} | {measured on N real units / stated by client} |
| Share of work that is interactive | {…%} | {…} |
| Share of work that can run in the background at a discount | {…%} | {…} |
| Discount on background work | {…%} | {pricing page, date checked} |
| Fee per {unit} | ${…} | {contract} |

*Production cost is modelled as measured cost per {unit} × scale factor, split between the interactive and background shares. If the scale factor is not measured, the annual-cost and margin rows are estimates; mark them as such.*

*Prices change. Check the current price list and write the date you checked it before quoting any figure that depends on it.*
