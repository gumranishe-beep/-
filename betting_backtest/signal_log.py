#!/usr/bin/env python3
"""
Журнал сигналов "на будущее", раз исторических данных с биржи/sofascore
нет (сеть закрыта). Логика: каждый сигнал фиксируется с результатом
"pending" до окончания события, затем закрывается командой settle.
Закрытые записи экспортируются в формат, который понимает backtest.py.

Один файл-журнал signal_log.csv, никакой сети, только ручной ввод.
"""

import argparse
import csv
import os

FIELDS = ["id", "date", "event", "market", "odds", "prob", "closing_odds", "status", "result"]
LOG_PATH = os.path.join(os.path.dirname(__file__), "signal_log.csv")


def _load_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save_rows(path: str, rows: list[dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def cmd_add(args):
    rows = _load_rows(LOG_PATH)
    next_id = (max((int(r["id"]) for r in rows), default=0)) + 1
    rows.append(
        {
            "id": next_id,
            "date": args.date,
            "event": args.event,
            "market": args.market or "",
            "odds": args.odds,
            "prob": args.prob,
            "closing_odds": "",
            "status": "pending",
            "result": "",
        }
    )
    _save_rows(LOG_PATH, rows)
    ev = args.prob * args.odds - 1.0
    print(f"Добавлен сигнал #{next_id}: {args.event} | odds={args.odds} prob={args.prob} EV={ev:+.3f} -> pending")


def cmd_settle(args):
    rows = _load_rows(LOG_PATH)
    target = None
    for r in rows:
        if int(r["id"]) == args.id:
            target = r
            break
    if target is None:
        print(f"Сигнал с id={args.id} не найден.")
        return
    if target["status"] != "pending":
        print(f"Сигнал #{args.id} уже закрыт (status={target['status']}).")
        return

    target["status"] = "settled"
    target["result"] = "1" if args.outcome == "win" else "0"
    if args.closing_odds is not None:
        target["closing_odds"] = str(args.closing_odds)

    _save_rows(LOG_PATH, rows)
    print(f"Сигнал #{args.id} закрыт: {args.outcome}")


def cmd_list(args):
    rows = _load_rows(LOG_PATH)
    if not rows:
        print("Журнал пуст.")
        return
    for r in rows:
        if args.status and r["status"] != args.status:
            continue
        print(f"#{r['id']:>3} [{r['status']:>8}] {r['date']} {r['event']:<35} "
              f"odds={r['odds']:<6} prob={r['prob']:<5} result={r['result']}")


def cmd_export(args):
    rows = _load_rows(LOG_PATH)
    settled = [r for r in rows if r["status"] == "settled"]
    if not settled:
        print("Нет закрытых (settled) сигналов для экспорта.")
        return
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "event", "market", "odds", "prob", "result", "closing_odds"])
        writer.writeheader()
        for r in settled:
            writer.writerow(
                {
                    "date": r["date"],
                    "event": r["event"],
                    "market": r["market"],
                    "odds": r["odds"],
                    "prob": r["prob"],
                    "result": r["result"],
                    "closing_odds": r["closing_odds"],
                }
            )
    print(f"Экспортировано {len(settled)} закрытых сигналов в {args.output}. "
          f"Можно сразу прогонять: python3 backtest.py {args.output}")


def main():
    ap = argparse.ArgumentParser(description="Журнал сигналов для накопления своей истории ставок")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Добавить новый сигнал (pending)")
    p_add.add_argument("--date", required=True, help="Дата события, YYYY-MM-DD")
    p_add.add_argument("--event", required=True, help="Название матча/события")
    p_add.add_argument("--market", default="", help="Рынок (например 'HT 0:0')")
    p_add.add_argument("--odds", type=float, required=True, help="Кэф на момент сигнала")
    p_add.add_argument("--prob", type=float, required=True, help="Оценка вероятности (0-1)")
    p_add.set_defaults(func=cmd_add)

    p_settle = sub.add_parser("settle", help="Закрыть сигнал после того, как событие прошло")
    p_settle.add_argument("--id", type=int, required=True, help="ID сигнала из списка")
    p_settle.add_argument("--outcome", choices=["win", "loss"], required=True)
    p_settle.add_argument("--closing-odds", type=float, default=None, help="Закрывающий кэф рынка (для CLV)")
    p_settle.set_defaults(func=cmd_settle)

    p_list = sub.add_parser("list", help="Показать журнал")
    p_list.add_argument("--status", choices=["pending", "settled"], default=None)
    p_list.set_defaults(func=cmd_list)

    p_export = sub.add_parser("export", help="Экспортировать settled-записи в формат backtest.py")
    p_export.add_argument("--output", default="my_history.csv")
    p_export.set_defaults(func=cmd_export)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
