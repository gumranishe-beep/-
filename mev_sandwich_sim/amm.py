"""
Minimal constant-product AMM (Uniswap v2 style), purely in-memory.

No chain, no RPC, no mempool, no private keys. This models a single
liquidity pool of two synthetic assets X and Y so that sandwich-attack
mechanics can be studied on paper.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Pool:
    reserve_x: float
    reserve_y: float
    fee_bps: int = 30  # 0.30%, the Uniswap v2 default

    @property
    def fee_mult(self) -> float:
        return 1 - self.fee_bps / 10_000

    @property
    def price_x_in_y(self) -> float:
        """Spot price: how much Y one unit of X is worth."""
        return self.reserve_y / self.reserve_x

    def quote_x_for_y(self, dx: float) -> float:
        """Read-only quote: how much Y you'd receive for selling dx of X."""
        if dx <= 0:
            return 0.0
        dx_eff = dx * self.fee_mult
        return self.reserve_y * dx_eff / (self.reserve_x + dx_eff)

    def quote_y_for_x(self, dy: float) -> float:
        """Read-only quote: how much X you'd receive for selling dy of Y."""
        if dy <= 0:
            return 0.0
        dy_eff = dy * self.fee_mult
        return self.reserve_x * dy_eff / (self.reserve_y + dy_eff)

    def swap_x_for_y(self, dx: float) -> float:
        """Execute: sell dx of X, receive dy of Y. Mutates reserves."""
        dy = self.quote_x_for_y(dx)
        self.reserve_x += dx
        self.reserve_y -= dy
        return dy

    def swap_y_for_x(self, dy: float) -> float:
        """Execute: sell dy of Y, receive dx of X. Mutates reserves."""
        dx = self.quote_y_for_x(dy)
        self.reserve_y += dy
        self.reserve_x -= dx
        return dx

    def copy(self) -> "Pool":
        return Pool(self.reserve_x, self.reserve_y, self.fee_bps)
