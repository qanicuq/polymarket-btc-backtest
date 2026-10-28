# polymarket-btc-backtest

Research backtest: does buying the ~1¢ side of Polymarket's "Bitcoin Up or Down" 5-minute markets make money after
realistic fills and fees?

- Data: the free public [PMXT order-book archive](https://archive.pmxt.dev) and Polymarket's public Gamma API.
- Paper research only: no trading, no accounts, no API keys. Everything runs in GitHub Actions.

## What's here
- `coverage/`: which archive hours actually contain these markets (made by `scripts/coverage.py`).
- Backtest code and results will be added after the validation step passes.

**Result (Oct 16, 2026): shelved.** The only profit came from one unusual stretch (Apr 21 – May 4, 2026). Every other
day lost money at realistic order delays. See [CONCLUSION.md](CONCLUSION.md).

## Favorites backtest (Oct 25, 2026): "buy the obvious side at 70-90c" does not work
224,892 resolved Polymarket markets (>= $10k volume, Jul 2025 - Oct 2026). Buying the favorite at 70-90c, 24 hours
before the scheduled end, and holding: favorites won about 4-5 points LESS often than their price said (favorites bought at 80-90c, about
85c on average, won only 80% of the time). Test months (Jul-Oct 2026), with a 2c cost: -10.5% per bet;
every month lost money. A no-skill baseline (buy every side 10-90c) was about break-even. The best rule picked on
training data (7 days out, 95-99c) also lost in the test months (-2.0%). Held up when split by side, volume, market
type, and one bet per event. Limit: prices are Polymarket's price history, not the real ask.
Details: [favorites/RESULTS.md](favorites/RESULTS.md).

## Where @bigggggggg's profit came from (Oct 25, 2026; [trader/REPORT.md](trader/REPORT.md))
Not from holding obvious winners to $1: of $14.1M bought, only $12K was ever redeemed at the end. Instead, $12.8M went
through 13,963 "conversions" and $0.47M through merges: swapping a full set of shares in a multi-outcome event back
into cash, which pays off when the prices across all outcomes don't add up. 150,057 trades in 162 days (median $6,
2 seconds apart) = an automated arbitrage bot. Rewards + rebates: about $38K. Note: per-position P/L numbers are
distorted by conversions (they sum to $2.06M vs the profile's $765K), so the report's by-price tables aren't reliable.
