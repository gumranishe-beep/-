#!/usr/bin/env python3
"""
Бэктест стратегии ставок по историческим сигналам.

Вход: CSV со столбцами (см. README.md в этой папке).
Логика: для каждой строки считается EV по вашей вероятности и взятому кэфу,
решение "ставить/пропустить" принимается по тому же правилу, что и в живом
анализе (EV > 0), размер ставки — по выбранному режиму стейкинга,
банкролл обновляется по фактическому результату (result).

Никаких внешних запросов скрипт не делает — все данные только из CSV.
"""

import argparse
import csv
import statistics
from dataclasses import dataclass, field


@dataclass
class BetRecord:
    date: str
    event: str
    market: str
    odds: float
    prob: float
    result: int  # 1 = выиграла, 0 = проиграла
    closing_odds: float | None = None


@dataclass
class SimResult:
    bankroll_curve: list[float] = field(default_factory=list)
    taken: list[dict] = field(default_factory=list)
    skipped_count: int = 0


def implied_probability(odds: float) -> float:
    return 1.0 / odds


def expected_value(prob: float, odds: float) -> float:
    return prob * odds - 1.0


def kelly_fraction(prob: float, odds: float) -> float:
    b = odds - 1.0
    if b <= 0:
        return 0.0
    f = (prob * odds - 1.0) / b
    return max(f, 0.0)


def overround(odds_list: list[float]) -> float:
    """Маржа букмекера по полному набору исходов одного рынка."""
    return (sum(1.0 / o for o in odds_list) - 1.0) * 100.0


def load_bets(path: str) -> list[BetRecord]:
    bets = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            closing = row.get("closing_odds", "").strip()
            bets.append(
                BetRecord(
                    date=row["date"],
                    event=row["event"],
                    market=row.get("market", ""),
                    odds=float(row["odds"]),
                    prob=float(row["prob"]),
                    result=int(row["result"]),
                    closing_odds=float(closing) if closing else None,
                )
            )
    return bets


def run_backtest(
    bets: list[BetRecord],
    bankroll_start: float,
    stake_mode: str,
    flat_pct: float,
    kelly_mult: float,
    max_pct: float,
    min_ev: float,
) -> SimResult:
    bankroll = bankroll_start
    sim = SimResult(bankroll_curve=[bankroll])

    for bet in bets:
        ev = expected_value(bet.prob, bet.odds)
        if ev <= min_ev:
            sim.skipped_count += 1
            continue

        if stake_mode == "flat":
            pct = flat_pct
        elif stake_mode == "kelly":
            pct = kelly_fraction(bet.prob, bet.odds) * kelly_mult * 100.0
        else:
            raise ValueError(f"unknown stake_mode: {stake_mode}")

        pct = min(pct, max_pct)
        stake = bankroll * (pct / 100.0)

        if bet.result == 1:
            profit = stake * (bet.odds - 1.0)
        else:
            profit = -stake

        bankroll += profit

        clv_pct = None
        if bet.closing_odds:
            clv_pct = (implied_probability(bet.closing_odds) - implied_probability(bet.odds)) \
                / implied_probability(bet.closing_odds) * 100.0

        sim.taken.append(
            {
                "date": bet.date,
                "event": bet.event,
                "odds": bet.odds,
                "prob": bet.prob,
                "ev": ev,
                "stake": stake,
                "stake_pct": pct,
                "result": bet.result,
                "profit": profit,
                "bankroll_after": bankroll,
                "clv_pct": clv_pct,
            }
        )
        sim.bankroll_curve.append(bankroll)

    return sim


def max_drawdown_pct(curve: list[float]) -> float:
    peak = curve[0]
    worst = 0.0
    for v in curve:
        peak = max(peak, v)
        dd = (peak - v) / peak * 100.0 if peak > 0 else 0.0
        worst = max(worst, dd)
    return worst


def longest_losing_streak(taken: list[dict]) -> int:
    longest = cur = 0
    for b in taken:
        if b["result"] == 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return longest


def print_report(sim: SimResult, bankroll_start: float):
    taken = sim.taken
    n = len(taken)
    if n == 0:
        print("Нет ставок, прошедших фильтр EV > 0. Проверьте входные данные.")
        return

    wins = sum(1 for b in taken if b["result"] == 1)
    total_staked = sum(b["stake"] for b in taken)
    total_profit = sum(b["profit"] for b in taken)
    roi = total_profit / total_staked * 100.0 if total_staked else 0.0
    avg_ev = statistics.mean(b["ev"] for b in taken)
    clv_values = [b["clv_pct"] for b in taken if b["clv_pct"] is not None]

    print("=" * 60)
    print("РЕЗУЛЬТАТЫ БЭКТЕСТА")
    print("=" * 60)
    print(f"Сигналов всего:           {n + sim.skipped_count}")
    print(f"Пропущено (EV <= порога): {sim.skipped_count}")
    print(f"Ставок сделано:           {n}")
    print(f"Выиграно / проиграно:     {wins} / {n - wins}")
    print(f"Winrate:                  {wins / n * 100:.1f}%")
    print(f"Банкролл старт -> финиш:  {bankroll_start:.2f} -> {sim.bankroll_curve[-1]:.2f}")
    print(f"ROI (прибыль/оборот):     {roi:.2f}%")
    print(f"Прибыль абсолютная:       {total_profit:+.2f}")
    print(f"Средний EV ставки:        {avg_ev:+.3f}")
    print(f"Макс. просадка банка:     {max_drawdown_pct(sim.bankroll_curve):.1f}%")
    print(f"Самая длинная серия минусов: {longest_losing_streak(taken)}")
    if clv_values:
        beat_closing = sum(1 for v in clv_values if v > 0)
        print(f"CLV в среднем:            {statistics.mean(clv_values):+.2f}%")
        print(f"Побед над закрывающей линией: {beat_closing}/{len(clv_values)} "
              f"({beat_closing / len(clv_values) * 100:.1f}%)")
    else:
        print("CLV:                      нет данных (closing_odds не указаны)")
    print("=" * 60)
    if n < 500:
        print(f"⚠ Выборка {n} ставок — статистически мало. Для надёжных выводов "
              f"по этой стратегии нужно 500+ ставок (см. раздел 8 инструкции).")


def main():
    ap = argparse.ArgumentParser(description="Бэктест стратегии ставок по CSV с сигналами")
    ap.add_argument("input", help="Путь к CSV с историческими сигналами и результатами")
    ap.add_argument("--bankroll", type=float, default=10000.0, help="Стартовый банк")
    ap.add_argument("--stake-mode", choices=["flat", "kelly"], default="flat")
    ap.add_argument("--flat-pct", type=float, default=2.0, help="% банка на ставку в режиме flat")
    ap.add_argument("--kelly-mult", type=float, default=0.5, help="Множитель дробного Келли (0.25 / 0.5 / 1.0)")
    ap.add_argument("--max-pct", type=float, default=5.0, help="Жёсткий потолок % банка на одну ставку")
    ap.add_argument("--min-ev", type=float, default=0.0, help="Минимальный EV для входа в ставку")
    ap.add_argument("--export", help="Путь для сохранения подробного CSV по каждой ставке")
    args = ap.parse_args()

    bets = load_bets(args.input)
    sim = run_backtest(
        bets,
        bankroll_start=args.bankroll,
        stake_mode=args.stake_mode,
        flat_pct=args.flat_pct,
        kelly_mult=args.kelly_mult,
        max_pct=args.max_pct,
        min_ev=args.min_ev,
    )
    print_report(sim, args.bankroll)

    if args.export and sim.taken:
        fieldnames = list(sim.taken[0].keys())
        with open(args.export, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sim.taken)
        print(f"\nПодробный лог ставок сохранён в {args.export}")


if __name__ == "__main__":
    main()
