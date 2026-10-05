"""
Turn outputs/results.csv (from simulate.py) into two static charts for the
research write-up:

  1. outputs/victim_loss_vs_size.png
     Victim's loss (% of what they'd have received with no bot present),
     binned by trade size as a % of pool depth, one line per slippage-
     tolerance scenario.

  2. outputs/attack_outcomes.png
     Per scenario: share of trades the bot actually attacked, and among
     those, the share that still reverted (slippage protection held).

Static matplotlib PNGs (for embedding in a paper), not an interactive page.
Colors are the dataviz-skill categorical palette, used in fixed order.
"""

from __future__ import annotations

import csv
from collections import defaultdict

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_PATH = "outputs/results.csv"

# Fixed-order categorical palette (dataviz skill default), light mode.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def load_rows():
    with open(RESULTS_PATH, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(INK_MUTED)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9)


def chart_loss_vs_size(rows):
    fig, ax = plt.subplots(figsize=(7.5, 5), facecolor=SURFACE)
    style_axes(ax)

    scenarios = sorted({float(r["slippage_tolerance_pct"]) for r in rows})
    bin_edges = np.logspace(np.log10(0.002), np.log10(8), 18)  # % of pool

    for color, slip in zip(SERIES_COLORS, scenarios):
        sub = [r for r in rows if float(r["slippage_tolerance_pct"]) == slip]
        sizes = np.array([float(r["trade_size_pct_of_reserve"]) for r in sub])
        losses = np.array([float(r["victim_loss_pct"]) for r in sub])

        bin_idx = np.digitize(sizes, bin_edges)
        xs, ys = [], []
        for b in range(1, len(bin_edges)):
            mask = bin_idx == b
            if mask.sum() < 5:
                continue
            xs.append(np.median(sizes[mask]))
            ys.append(np.median(losses[mask]))

        label = "no slippage limit" if slip >= 100 else f"{slip:g}% victim slippage limit"
        ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=4, label=label)

    ax.set_xscale("log")
    ax.set_xlabel("Victim trade size (% of pool depth)", color=INK_SECONDARY, fontsize=10)
    ax.set_ylabel("Victim loss vs. no-attack baseline (%)", color=INK_SECONDARY, fontsize=10)
    ax.set_title(
        "Simulated sandwich harm by victim trade size and slippage protection",
        color=INK_PRIMARY,
        fontsize=12,
        loc="left",
        pad=12,
    )
    legend = ax.legend(frameon=False, fontsize=9, loc="upper left")
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    fig.tight_layout()
    fig.savefig("outputs/victim_loss_vs_size.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def chart_attack_outcomes(rows):
    scenarios = sorted({float(r["slippage_tolerance_pct"]) for r in rows})
    attacked_rate, revert_rate = [], []
    for slip in scenarios:
        sub = [r for r in rows if float(r["slippage_tolerance_pct"]) == slip]
        attacked = [r for r in sub if r["attacked"] == "True"]
        attacked_rate.append(100.0 * len(attacked) / len(sub))
        if attacked:
            reverted = [r for r in attacked if r["victim_reverted"] == "True"]
            revert_rate.append(100.0 * len(reverted) / len(attacked))
        else:
            revert_rate.append(0.0)

    labels = ["no limit" if s >= 100 else f"{s:g}%" for s in scenarios]
    x = np.arange(len(scenarios))
    width = 0.36

    fig, ax = plt.subplots(figsize=(7.5, 4.8), facecolor=SURFACE)
    style_axes(ax)

    ax.bar(x - width / 2, attacked_rate, width, color=SERIES_COLORS[0], label="trades the bot attacked")
    ax.bar(x + width / 2, revert_rate, width, color=SERIES_COLORS[1], label="of those, victim tx reverted")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, color=INK_SECONDARY, fontsize=9)
    ax.set_xlabel("Victim slippage tolerance", color=INK_SECONDARY, fontsize=10)
    ax.set_ylabel("Share of simulated trades (%)", color=INK_SECONDARY, fontsize=10)
    ax.set_title(
        "How often the bot attacks, and how often slippage protection still blocks it",
        color=INK_PRIMARY,
        fontsize=11,
        loc="left",
        pad=12,
    )
    legend = ax.legend(frameon=False, fontsize=9, loc="upper right")
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    fig.tight_layout()
    fig.savefig("outputs/attack_outcomes.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def print_summary(rows):
    scenarios = sorted({float(r["slippage_tolerance_pct"]) for r in rows})
    print("\nSummary by slippage-tolerance scenario:")
    print(f"{'scenario':>18} {'attacked %':>11} {'revert %':>9} {'median loss % (attacked)':>26}")
    for slip in scenarios:
        sub = [r for r in rows if float(r["slippage_tolerance_pct"]) == slip]
        attacked = [r for r in sub if r["attacked"] == "True"]
        reverted = [r for r in attacked if r["victim_reverted"] == "True"]
        losses = [float(r["victim_loss_pct"]) for r in attacked]
        label = "no limit" if slip >= 100 else f"{slip:g}%"
        med_loss = np.median(losses) if losses else 0.0
        print(
            f"{label:>18} {100*len(attacked)/len(sub):>10.1f}% "
            f"{100*len(reverted)/len(attacked) if attacked else 0:>8.1f}% {med_loss:>25.3f}%"
        )


def main():
    rows = load_rows()
    chart_loss_vs_size(rows)
    chart_attack_outcomes(rows)
    print_summary(rows)
    print("\nWrote outputs/victim_loss_vs_size.png and outputs/attack_outcomes.png")


if __name__ == "__main__":
    main()
