# polymarket-btc-backtest - instructions for Claude (and Grok)

PUBLIC repo. Research backtest of Polymarket "Bitcoin Up or Down" 5-minute markets (buying the ~1c side).
Runs only in GitHub Actions on public data. No trading, no accounts, no API keys.

## Rules
- This repo is PUBLIC. Never commit or print secrets. The ntfy topic lives ONLY in the Actions secret `NTFY_TOPIC`:
  workflows read `${{ secrets.NTFY_TOPIC }}` into an env var and never echo it. Never write the topic in any file,
  commit message, issue, or log line.
- Workflows trigger only on push to main, manual dispatch, or `workflow_run` of THIS repo's own workflows (the full
  backtest starts itself when the coverage scan completes). Never add pull_request / pull_request_target triggers.
- Notifications: ntfy push only, never email.
- Never commit raw parquet files or any file over ~5 MB.
- Be polite to the free PMXT archive: at most 6 parallel downloads across all workflows running at once.
- Strategy prompts and private notes stay in the owner's private repo qanicuq/btc-bot (`grok/handoff/`), not here.

## Layout
- `scripts/coverage.py` + `.github/workflows/coverage.yml`: request a scan by committing a new timestamp to
  `requests/coverage`; finished hours are skipped, so re-running resumes. Output: `coverage/coverage_<chunk>.csv`
  (one row per hour; `windows_in_file` = 0-12) and `coverage/windows_<chunk>.jsonl` (one line per 5-minute window
  with tokens, outcomes, `outcome_prices` (winner = "1"), and `in_file`). Use these instead of re-querying Gamma.
- `scripts/backtest.py HOUR OUTDIR`: one hour -> `OUTDIR/hour_HOUR.json` (additive sums, errors) and
  `OUTDIR/entries_HOUR.csv`. `scripts/summarize.py OUTDIR` pools them -> `SUMMARY.md`, `pooled.json` (ratios and
  Wilson 95% intervals are computed only after pooling). Core logic `run_token` is pure Python and unit-testable.
- `.github/workflows/validate.yml`: the 8 fixed validation hours (commit to `requests/validate` to run).
  `backtest.py` skips hours whose `hour_*.json` already finished without errors (set FORCE=1 to redo).
- `.github/workflows/full.yml` + `scripts/run_batch.py`: every hour that `coverage/` lists with windows, in weekly
  chunks (4 at a time), pushing results to `results/full/` every 20 hours; re-run (commit to `requests/full`) to
  resume. Grid: P 1c/2c, S $25/$100, delay L 0/0.25/0.5/1/3 s, plus per-cell splits by trigger time in the window.
- `results/validation/`: the 8 fixed validation hours (L 0/1/3 only; 2026-06-07T14 could not be downloaded: the
  archive stalls at ~270 of 505 MB).
- `scripts/pmxt_fetch.py`: ALWAYS download archive files with `fetch()`. Downloads really do stall part-way
  (2026-06-07T14: 201 MB in 3 s, then a trickle); `fetch` reconnects and resumes with HTTP Range and verifies size.

- Favorites backtest ("buy the 70-90c favorite, hold to the end", all resolved markets, not just BTC):
  `scripts/favorites_fetch.py YYYY-MM` -> `favorites/markets_YYYY-MM.csv.gz` (Gamma + CLOB prices-history, resumable; entry times count back from the
  SCHEDULED end, never the actual close, which would peek at the result);
  `scripts/favorites_backtest.py` -> `favorites/RESULTS.md`. Run via `favorites.yml` by committing to
  `requests/favorites` (first line `probe` = one month, 100 markets). Train < 2026-07, test >= 2026-07.

- `scripts/trader_profile.py WALLET` + `trader.yml` (commit to `requests/trader`): one public trader's closed
  positions and activity by type -> `trader/REPORT.md`. Data-api `activity` offset caps at 5000, so it splits time windows.

## Verified data facts (from the private btc-bot probe, Oct 2026)
- `price_change.size` = NEW total size at that price (0 removes the level); `side` BUY = bids, SELL = asks.
- Order rows by `timestamp` (exchange ms) with a STABLE sort on (timestamp, file position). File order is not time
  order; `timestamp_received` is a coarse batch time - never order by it.
- A rebuilt book drifts (69-93% level agreement with the next snapshot), so anchor it to each row's
  `best_bid` / `best_ask`. Do not apply `last_trade_price` rows to the book.
- `fee_rate_bps` on trade rows was 1000 in April and 0 in May 2026 for these markets; current docs say Crypto taker
  fee = shares x 0.07 x p x (1-p). Unresolved: always report gross and with-fee results.

---

# Coding guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Owner's Working Rules (added 2026-10-24)

The owner is not a programmer. Keep explanations plain and solutions simple.

- **Verify before calling it done.** Run it (test, dry run, backtest, or compare output before vs. after) and say exactly how it was checked. Unverified = not done.
- **If a fix feels hacky, scrap it** and write the simple, clean solution instead.
- **If things go sideways, stop and re-plan.** Don't keep pushing a broken approach.
- **Secrets stay secret.** The ntfy topic lives only in a GitHub secret — never in files, commits, or logs.
- **Notifications are ntfy push only.** Never email.
- **Everything runs in the cloud,** never on the owner's computer.
- **Save GitHub Actions minutes** (2,000/month limit): no unneeded runs; put `[skip ci]` in docs-only commit messages.
- **Keep this file short.** Delete rules that no longer matter.

## Lessons Learned

After any correction from the owner, add one line here so the mistake isn't repeated.
Format: `- YYYY-MM-DD: what went wrong → the rule now`

- (none yet)
