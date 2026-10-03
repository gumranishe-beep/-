#!/usr/bin/env python3
"""
Автозакрытие pending-сигналов в signal_log.csv по факту результата
через эндпоинт /scores The Odds API. Работает только для записей,
у которых есть sport_key/home_team/away_team (то есть залогированных
программно через value_scanner.py --auto-log) - вручную добавленные
через `signal_log.py add` без этих полей не трогает, их закрывать
нужно вручную через `signal_log.py settle`.

Внимание: эндпоинт /scores стоит 2 кредита квоты за вид спорта за вызов
(вдвое дороже /odds) - запрашиваем только те sport_key, по которым
реально есть pending-записи, не весь список.
"""

import sys

import requests

from signal_log import _load_rows, _save_rows
from value_scanner import BASE, load_api_key

DAYS_FROM = 3  # максимум, который принимает API - события старше не вернёт


def fetch_scores(api_key: str, sport_key: str) -> list[dict]:
    resp = requests.get(
        f"{BASE}/sports/{sport_key}/scores/",
        params={"apiKey": api_key, "daysFrom": DAYS_FROM},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def determine_result(selection: str, home_team: str, away_team: str, scores: list[dict]) -> int | None:
    """Возвращает 1/0 для selection, или None если не удалось сопоставить."""
    by_name = {s["name"]: int(s["score"]) for s in scores}
    if home_team not in by_name or away_team not in by_name:
        return None
    home_score = by_name[home_team]
    away_score = by_name[away_team]

    if selection == "Draw":
        return 1 if home_score == away_score else 0
    if selection == home_team:
        return 1 if home_score > away_score else 0
    if selection == away_team:
        return 1 if away_score > home_score else 0
    return None  # исход не совпал ни с одним известным именем - не рискуем угадывать


def main():
    api_key = load_api_key()
    rows = _load_rows()

    pending = [r for r in rows if r["status"] == "pending" and r["sport_key"] and r["home_team"]]
    if not pending:
        print("Нет программно залогированных pending-сигналов для автозакрытия "
              "(вручную добавленные закрывайте через signal_log.py settle).")
        return

    sport_keys = sorted({r["sport_key"] for r in pending})
    print(f"Проверяю результаты по {len(sport_keys)} вид(ам) спорта "
          f"({len(sport_keys)*2} кредитов квоты)...", file=sys.stderr)

    settled_count = 0
    for sport_key in sport_keys:
        try:
            scores_data = fetch_scores(api_key, sport_key)
        except requests.HTTPError as e:
            print(f"[{sport_key}] ошибка запроса scores: {e}", file=sys.stderr)
            continue

        by_match = {}
        for ev in scores_data:
            if ev.get("completed") and ev.get("scores"):
                by_match[(ev["home_team"], ev["away_team"])] = ev["scores"]

        for r in pending:
            if r["sport_key"] != sport_key or r["status"] != "pending":
                continue
            key = (r["home_team"], r["away_team"])
            scores = by_match.get(key)
            if scores is None:
                continue  # матч ещё не завершён или не найден в окне daysFrom

            result = determine_result(r["selection"], r["home_team"], r["away_team"], scores)
            if result is None:
                print(f"[#{r['id']}] не смог сопоставить исход '{r['selection']}' со счётом {scores}, "
                      f"пропускаю - закройте вручную.", file=sys.stderr)
                continue

            r["status"] = "settled"
            r["result"] = str(result)
            settled_count += 1
            print(f"#{r['id']} {r['event']} | {r['selection']} -> "
                  f"{'WIN' if result else 'LOSS'} (авто, по /scores)")

    if settled_count:
        _save_rows(rows)
    print(f"\nЗакрыто автоматически: {settled_count} из {len(pending)} pending-сигналов.")


if __name__ == "__main__":
    main()
