# Pricing

**Verified on: 2026-10-30** from https://platform.claude.com/docs/en/about-claude/pricing and
https://platform.claude.com/docs/en/build-with-claude/prompt-caching

**Prices change. Re-check the pricing page before quoting any figure to a client, and update the date and
table here when you do.** The table below is read by `templates/cost.py`; keep its layout (a row per model,
dollar amounts per million tokens, model id in backticks in the first column).

| model id | input | cache write 5m | cache write 1h | cache read | output | min cacheable prefix (tokens) |
|---|---|---|---|---|---|---|
| `claude-fable-5-1` | 10.00 | 12.50 | 20.00 | 0.25 | 50.00 | 512 |
| `claude-opus-5-5` | 4.00 | 5.00 | 8.00 | 0.20 | 20.00 | 512 |
| `claude-opus-4-8` | 5.00 | 6.25 | 10.00 | 0.50 | 25.00 | 1024 |
| `claude-sonnet-5-5` | 2.00 | 2.50 | 4.00 | 0.10 | 10.00 | 512 |
| `claude-sonnet-5` | 2.00 | 2.50 | 4.00 | 0.20 | 10.00 | 1024 |
| `claude-haiku-5-5` | 0.10 | 0.125 | 0.20 | 0.01 | 0.50 | 512 |
| `claude-haiku-5-5@>100k` | 0.50 | 0.625 | 1.00 | 0.05 | 2.50 | 512 |
| `claude-haiku-4-5` | 1.00 | 1.25 | 2.00 | 0.10 | 5.00 | 4096 |

Notes:

- Rows ending `@>100k` apply to a request with more than 100,000 input tokens (only Haiku 5.5 has a long-prompt tier).
- **Cache read is not always 0.1x input.** It is 0.05x for Opus 5.5 and Sonnet 5.5, and 0.025x for Fable 5.1. Always take the rate from the table, never assume a multiplier.
- Cache writes at the default 5-minute lifetime cost 1.25x input; the 1-hour lifetime costs 2x input.
- **Batch API: 50% off all token charges** (input, output, and the cache rates stack with it).
- Only models whose id was confirmed are listed (other models, such as Opus 5 and Sonnet 4.6, also appear on the pricing page). For any other model, look up the id and rates on the pricing page and add a row; don't guess. The `claude-api` skill lists current ids.
- Claude 4.7 and later models use a tokenizer that produces about 30% more tokens for the same text than earlier models, so a cheaper per-token model is not always cheaper per document. Measure, don't extrapolate.
- Minimum cacheable prefix: prompts shorter than this are not cached and no error is returned. Confirm with `usage.cache_read_input_tokens`.
- Fast mode and data-residency options have their own multipliers; they aren't in this table.
