"""
Sandwich-attack mechanics, simulated against the in-memory Pool from amm.py.

Everything here runs on paper: a "victim" trade is just a (direction, size)
tuple fed into the simulated pool, never a real pending transaction on a
real network. The bot never touches a wallet, a mempool, or an RPC endpoint.

Research use: this lets you measure, under a controlled and reproducible
model, how much value a sandwich extracts from a victim trade as a function
of trade size, pool depth, fee tier, gas cost, and the victim's slippage
tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass

from amm import Pool


def _max_frontrun_within_slippage(
    pool: Pool, dx_victim: float, min_out: float, hi_cap: float, iters: int = 60
) -> float:
    """
    Largest front-run size (buying Y with X, same direction as the victim)
    such that the victim's trade still clears their own min_out.

    victim_out(dx_f) is monotonically decreasing in dx_f, so this is a
    plain binary search.
    """

    def victim_out(dx_f: float) -> float:
        p = pool.copy()
        p.swap_x_for_y(dx_f)
        return p.quote_x_for_y(dx_victim)

    if victim_out(0.0) < min_out:
        # Victim is already at/under their own tolerance with no attack at all
        # (e.g. min_out was set above the true baseline) -- nothing to search.
        return 0.0

    lo, hi = 0.0, hi_cap
    for _ in range(iters):
        mid = (lo + hi) / 2
        if victim_out(mid) >= min_out:
            lo = mid
        else:
            hi = mid
    return lo


def _bot_profit(pool: Pool, dx_victim: float, dx_frontrun: float) -> float:
    """Profit in units of X for a given front-run size, ignoring gas."""
    p = pool.copy()
    dy_f = p.swap_x_for_y(dx_frontrun)  # front-run buy
    p.swap_x_for_y(dx_victim)  # victim buy, now at worse price
    dx_back = p.swap_y_for_x(dy_f)  # back-run sell
    return dx_back - dx_frontrun


def _optimal_frontrun(
    pool: Pool, dx_victim: float, hi_cap: float, iters: int = 80
) -> tuple[float, float]:
    """Ternary search for the profit-maximizing front-run size on [0, hi_cap].

    Profit(dx_f) is unimodal over this range (rises, peaks, falls back toward
    zero as the front-run itself eats the spread), so ternary search finds
    the maximum reliably without needing a closed-form derivative.
    """
    lo, hi = 0.0, hi_cap
    for _ in range(iters):
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3
        if _bot_profit(pool, dx_victim, m1) < _bot_profit(pool, dx_victim, m2):
            lo = m1
        else:
            hi = m2
    dx_f = (lo + hi) / 2
    return dx_f, _bot_profit(pool, dx_victim, dx_f)


@dataclass
class SandwichResult:
    dx_victim: float
    dx_frontrun: float
    victim_out_baseline: float  # what the victim would get with no attack
    victim_out_attacked: float  # what the victim actually gets
    victim_loss_y: float
    victim_loss_pct: float
    bot_profit_x: float
    bot_profit_x_after_gas: float
    gas_cost_x: float
    attacked: bool
    victim_reverted: bool


def simulate_sandwich(
    pool: Pool,
    dx_victim: float,
    slippage_tolerance_pct: float = 100.0,
    gas_cost_x: float = 0.0,
    min_profit_after_gas: float = 0.0,
) -> SandwichResult:
    """
    Simulate one victim trade (buying Y with dx_victim of X) against `pool`,
    optionally sandwiched by a profit-maximizing bot.

    slippage_tolerance_pct: the victim's own max acceptable slippage, e.g.
        0.5 means they revert if they'd receive <0.5% less than spot quote.
        100.0 effectively disables the protection (victim accepts anything).
    gas_cost_x: round-trip gas cost of the front-run + back-run bundle, in
        units of X, charged against the bot's profit.
    min_profit_after_gas: the bot only attacks if profit after gas clears
        this bar; otherwise it does nothing (models a bot that skips
        unprofitable targets rather than attacking at a loss).

    A Flashbots-style bundle is atomic: either both bot legs AND the victim
    leg land, or none of them do. So if the profit-maximizing front-run
    would push the victim past their own slippage tolerance, a rational bot
    scales the front-run back to the largest size that still lets the
    victim's trade clear -- pushing it further would just cause the whole
    bundle to revert and land nothing.
    """
    baseline_out = pool.quote_x_for_y(dx_victim)
    min_out = baseline_out * (1 - slippage_tolerance_pct / 100.0)

    hi_cap = pool.reserve_x * 10  # generous search ceiling
    unconstrained_dx_f, _ = _optimal_frontrun(pool, dx_victim, hi_cap)

    # Check whether the unconstrained optimum would blow through the
    # victim's slippage tolerance; if so, cap it.
    check_pool = pool.copy()
    check_pool.swap_x_for_y(unconstrained_dx_f)
    victim_out_if_unconstrained = check_pool.quote_x_for_y(dx_victim)

    if victim_out_if_unconstrained >= min_out:
        dx_f = unconstrained_dx_f
    else:
        dx_f = _max_frontrun_within_slippage(pool, dx_victim, min_out, hi_cap)

    profit_before_gas = _bot_profit(pool, dx_victim, dx_f)
    profit_after_gas = profit_before_gas - gas_cost_x

    attacked = dx_f > 0 and profit_after_gas >= min_profit_after_gas
    if not attacked:
        dx_f = 0.0

    live = pool.copy()
    dy_f = live.swap_x_for_y(dx_f) if dx_f > 0 else 0.0
    victim_out_attacked = live.swap_x_for_y(dx_victim)
    victim_reverted = victim_out_attacked < min_out - 1e-12

    if dx_f > 0:
        dx_back = live.swap_y_for_x(dy_f)
        bot_profit = dx_back - dx_f
    else:
        dx_back = 0.0
        bot_profit = 0.0

    loss_y = baseline_out - victim_out_attacked
    loss_pct = (loss_y / baseline_out * 100.0) if baseline_out > 0 else 0.0

    return SandwichResult(
        dx_victim=dx_victim,
        dx_frontrun=dx_f,
        victim_out_baseline=baseline_out,
        victim_out_attacked=victim_out_attacked,
        victim_loss_y=loss_y,
        victim_loss_pct=loss_pct,
        bot_profit_x=bot_profit,
        bot_profit_x_after_gas=bot_profit - gas_cost_x if dx_f > 0 else 0.0,
        gas_cost_x=gas_cost_x if dx_f > 0 else 0.0,
        attacked=dx_f > 0,
        victim_reverted=victim_reverted,
    )
