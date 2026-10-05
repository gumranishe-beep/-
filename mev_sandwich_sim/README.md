# MEV Sandwich-Attack Simulator (paper trading / research only)

A fully synthetic, offline simulation of a sandwich attack on a constant-product
AMM pool (Uniswap v2 style). Built to study **how much value a sandwich bot can
extract from a victim trade**, as a function of trade size, pool depth, fee
tier, gas cost, and the victim's slippage protection — for a research write-up
on the harm these bots cause to ordinary traders.

## What this is NOT

- No real blockchain, RPC endpoint, wallet, or private key anywhere in this
  code.
- No mempool scanning — the "victim transaction" is just a `(direction, size)`
  tuple fed into an in-memory pool.
- Nothing here can execute a real trade or interact with a real exchange.

Everything is "paper trading": a closed-form/numeric model of pool reserves
and swap math, run entirely in memory, so you can measure the mechanism
without touching real markets or real counterparties.

## How the model works

- `amm.py` — a minimal constant-product pool (`x * y = k`, with a trading fee),
  matching Uniswap v2's swap formula.
- `attack.py` — the sandwich mechanics:
  1. A "victim" wants to buy token Y with `dx_v` of token X.
  2. The bot computes the profit-maximizing front-run size via ternary search
     (the profit curve is unimodal once a trading fee is present — see the
     derivation note below).
  3. If the victim has a slippage tolerance, and the profit-maximizing
     front-run would push the victim's trade past it, the bot **caps** its
     front-run at the largest size that still lets the victim's trade clear —
     because a real bundle (e.g. via Flashbots) is atomic: if the victim's leg
     would revert, the whole bundle fails to land and the bot gets nothing.
  4. If attacking isn't profitable after the assumed gas cost, the bot does
     nothing (`attacked=False`) — this models a rational bot skipping
     low-value targets rather than attacking at a loss.
- `simulate.py` — runs thousands of randomized victim trade sizes against a
  fixed pool, across a few slippage-tolerance scenarios, and writes
  `outputs/results.csv`.
- `analyze.py` — turns the CSV into two charts plus a text summary table.

## A finding worth noting for the write-up

With **no fee**, the math has no interior optimum: bot profit strictly
increases with front-run size and only approaches (never reaches) the
victim's own trade size as front-run capital goes to infinity. It's the
**trading fee** that creates a finite optimal front-run size — and that
optimum is often *much larger* than the victim's own trade (tens to hundreds
of times, in this model's default pool). This mirrors a well-documented
real-world pattern: sandwich bots commonly use flash loans to front huge
capital relative to the victim trade, because marginal extraction keeps
rising (just slowly) the more capital is put up.

## Running it

```bash
pip install -r requirements.txt
python3 simulate.py   # writes outputs/results.csv (~20k simulated trades)
python3 analyze.py    # writes outputs/*.png + prints a summary table
```

## Tunable assumptions (edit the constants at the top of `simulate.py`)

| Parameter | Meaning |
|---|---|
| `POOL_RESERVE_X` / `POOL_RESERVE_Y` | Synthetic pool depth and spot price |
| `FEE_BPS` | Pool fee tier (30 = 0.30%, the Uniswap v2 default) |
| `N_TRADES` | Simulated victim trades per slippage scenario |
| `GAS_COST_X` | Round-trip bundle gas cost, in X units, charged to the bot |
| `SLIPPAGE_SCENARIOS` | Victim slippage-tolerance settings to compare (%) |

## What the default run shows

With the default pool (5,000 X / 10,000,000 Y, 0.30% fee) and ~20k simulated
trades per scenario:

- **Without any slippage protection**, the median victim loss among trades
  the bot chooses to attack is close to total (~95%+ of the trade's value) —
  an idealized upper bound showing why slippage protection matters so much.
- **With slippage protection**, victim loss is capped almost exactly at the
  tolerance set (e.g. a 0.5% tolerance caps losses near 0.5%) — but the bot
  still extracts right up to that limit, every time it's profitable to do so.
  In this idealized model the bot never misjudges the boundary, so the
  victim's transaction essentially never reverts — slippage protection
  bounds the damage, but doesn't stop the extraction.
- The bot only attacks roughly the largest ~40% of trades in the simulated
  size distribution — gas cost makes sandwiching small retail-sized trades
  unprofitable, which matches the empirical pattern that sandwich attacks
  concentrate on larger trades.

## Extending this for the paper

- Vary `FEE_BPS` and `GAS_COST_X` to show how fee tier and gas price shift the
  profitable attack threshold.
- Model multiple competing searchers (a priority-gas-auction / highest-bid
  model) to show how competition erodes a single bot's profit.
- Feed in a trade-size distribution calibrated from public historical data
  (e.g. published MEV-Explore / Flashbots transparency datasets) instead of
  the synthetic log-uniform distribution, to ground the harm estimates in
  observed trade sizes.
