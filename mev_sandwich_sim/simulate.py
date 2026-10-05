"""
Batch runner: generates synthetic "victim" trades against a synthetic pool
and records what a profit-maximizing sandwich bot would do, purely on paper.

Usage:
    python simulate.py

Writes outputs/results.csv with one row per simulated victim trade.
"""

from __future__ import annotations

import csv
import random
from dataclasses import asdict

from amm import Pool
from attack import simulate_sandwich

OUTPUT_PATH = "outputs/results.csv"

# Pool + market assumptions -- all synthetic, tune freely for the paper.
POOL_RESERVE_X = 5_000.0  # e.g. "ETH" side
POOL_RESERVE_Y = 10_000_000.0  # e.g. "USDC" side -> spot price 2000 Y per X
FEE_BPS = 30

N_TRADES = 5_000
TRADE_SIZE_MIN = 0.1  # fraction-of-pool scenarios below
TRADE_SIZE_MAX_PCT_OF_RESERVE = 0.08  # victim trades up to 8% of pool depth

GAS_COST_X = 0.01  # round-trip bundle gas, in X units (e.g. ~0.01 ETH)
MIN_PROFIT_AFTER_GAS = 0.0  # bot attacks any trade that is profitable at all

# Victim slippage tolerance scenarios to compare, in percent.
SLIPPAGE_SCENARIOS = [0.5, 1.0, 3.0, 100.0]  # 100.0 == "no protection"

random.seed(7)


def random_trade_size() -> float:
    """Victim trade size in X, log-uniform up to TRADE_SIZE_MAX_PCT_OF_RESERVE of reserves."""
    max_size = POOL_RESERVE_X * TRADE_SIZE_MAX_PCT_OF_RESERVE
    # log-uniform so small/common trades and rare whale trades both get coverage
    lo, hi = TRADE_SIZE_MIN, max_size
    u = random.random()
    return lo * (hi / lo) ** u


def main() -> None:
    rows = []
    for slippage_pct in SLIPPAGE_SCENARIOS:
        for _ in range(N_TRADES):
            pool = Pool(POOL_RESERVE_X, POOL_RESERVE_Y, FEE_BPS)
            dx_v = random_trade_size()
            result = simulate_sandwich(
                pool,
                dx_victim=dx_v,
                slippage_tolerance_pct=slippage_pct,
                gas_cost_x=GAS_COST_X,
                min_profit_after_gas=MIN_PROFIT_AFTER_GAS,
            )
            row = asdict(result)
            row["slippage_tolerance_pct"] = slippage_pct
            row["trade_size_pct_of_reserve"] = dx_v / POOL_RESERVE_X * 100.0
            rows.append(row)

    fieldnames = list(rows[0].keys())
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} simulated trades to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
