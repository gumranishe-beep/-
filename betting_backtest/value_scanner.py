#!/usr/bin/env python3
"""
Сканер ценности по кросс-букмекерским кэфам (The Odds API).

Идея: вместо того, чтобы придумывать свою вероятность исхода (чего у нас
нет — ни модели, ни достаточно истории), берём в качестве "честной"
вероятности линию референсного букмекера (по умолчанию Pinnacle — исторически
самый точный и наименее маржинальный книжник), снимаем с неё маржу
(devigging), и ищем других букмекеров, которые на тот же исход дают кэф
выше этой справедливой цены. Расхождение между книжниками и есть ценность —
без необходимости самому предсказывать результат матча.

Это дополняет, а не заменяет качественный анализ (форма, H2H, травмы) —
чисто количественный фильтр "что вообще стоит разбирать дальше".
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import requests

BASE = "https://api.the-odds-api.com/v4"
REFERENCE_BOOK = "pinnacle"

# Высокотрастовый список по разделу 3.2 методологии: признанные топ-лиги и
# континентальные турниры, плюс тур-левел теннис (ATP/WTA/Большие шлемы).
# Нишевые/любительские/студенческие лиги и низколиквидные дивизионы сюда
# сознательно не входят - там расхождение кэфов между букмекерами чаще
# объясняется тонким рынком, а не реальной неэффективностью (см. раздел 3.2 -
# это зона риска, не зона ценности). Включить всё подряд - флаг --include-niche.
HIGH_TRUST_SOCCER = {
    "soccer_epl", "soccer_efl_champ", "soccer_england_league1", "soccer_england_efl_cup",
    "soccer_spain_la_liga", "soccer_spain_segunda_division",
    "soccer_italy_serie_a", "soccer_italy_serie_b",
    "soccer_germany_bundesliga", "soccer_germany_bundesliga2",
    "soccer_france_ligue_one", "soccer_france_ligue_two",
    "soccer_russia_premier_league",
    "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga",
    "soccer_belgium_first_div", "soccer_austria_bundesliga", "soccer_switzerland_superleague",
    "soccer_turkey_super_league",
    "soccer_brazil_campeonato", "soccer_usa_mls", "soccer_japan_j_league", "soccer_korea_kleague1",
    "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_uefa_europa_conference_league", "soccer_uefa_nations_league",
    "soccer_conmebol_copa_libertadores", "soccer_conmebol_copa_sudamericana",
}


def is_high_trust(sport_key: str) -> bool:
    if sport_key.startswith("tennis_atp") or sport_key.startswith("tennis_wta"):
        return True
    return sport_key in HIGH_TRUST_SOCCER


def load_api_key() -> str:
    key = os.environ.get("ODDS_API_KEY")
    if key:
        return key
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("ODDS_API_KEY="):
                    return line.strip().split("=", 1)[1]
    sys.exit("ODDS_API_KEY не найден ни в окружении, ни в .env")


def fetch_odds(api_key: str, sport_key: str, regions: str, markets: str) -> tuple[list, dict]:
    resp = requests.get(
        f"{BASE}/sports/{sport_key}/odds/",
        params={"apiKey": api_key, "regions": regions, "markets": markets, "oddsFormat": "decimal"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json(), resp.headers


def fetch_all_active_sports(api_key: str) -> list[str]:
    """Список активных sport_key для обычных матчей (без аутрайтов типа 'победитель лиги')
    это бесплатный запрос, квота не тратится."""
    resp = requests.get(f"{BASE}/sports/", params={"apiKey": api_key}, timeout=15)
    resp.raise_for_status()
    return [s["key"] for s in resp.json() if s["active"] and not s["has_outrights"]]


def devig_multiplicative(prices: dict) -> dict:
    """Снимает маржу пропорционально (multiplicative method)."""
    inv = {name: 1.0 / price for name, price in prices.items()}
    total = sum(inv.values())
    return {name: v / total for name, v in inv.items()}


def staleness_seconds(a: str, b: str) -> float:
    ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
    tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return abs((ta - tb).total_seconds())


def scan_event(event: dict, sport_key: str, market_key: str, min_ev: float, max_staleness_sec: float, max_odds: float) -> list[dict]:
    opportunities = []
    books = {b["key"]: b for b in event.get("bookmakers", [])}
    ref = books.get(REFERENCE_BOOK)
    if not ref:
        return opportunities

    ref_market = next((m for m in ref["markets"] if m["key"] == market_key), None)
    if not ref_market:
        return opportunities

    ref_prices = {o["name"]: o["price"] for o in ref_market["outcomes"]}
    if len(ref_prices) < 2:
        return opportunities
    # На экстремальных кэфах (разгромные мисматчи) devig занижает истинную маржу
    # из-за favorite-longshot bias - букмекеры кладут непропорционально больше
    # маржи именно в дальних андердогов. Там этот метод даёт ложные "value".
    if max(ref_prices.values()) > max_odds * 3:
        return opportunities
    fair = devig_multiplicative(ref_prices)

    for bkey, book in books.items():
        if bkey == REFERENCE_BOOK:
            continue
        market = next((m for m in book["markets"] if m["key"] == market_key), None)
        if not market:
            continue

        if staleness_seconds(ref_market["last_update"], market["last_update"]) > max_staleness_sec:
            continue  # кэфы обновлены не синхронно - разница может быть просто лагом, а не ценностью

        for outcome in market["outcomes"]:
            name = outcome["name"]
            price = outcome["price"]
            p = fair.get(name)
            if p is None:
                continue
            ev = p * price - 1.0
            if ev >= min_ev and price <= max_odds:
                opportunities.append(
                    {
                        "sport_key": sport_key,
                        "home_team": event["home_team"],
                        "away_team": event["away_team"],
                        "event": f"{event['home_team']} vs {event['away_team']}",
                        "commence_time": event["commence_time"],
                        "market": market_key,
                        "selection": name,
                        "bookmaker": book["title"],
                        "odds": price,
                        "fair_prob": p,
                        "implied_prob_taken": 1.0 / price,
                        "ev": ev,
                        "reference": REFERENCE_BOOK,
                    }
                )
    return opportunities


def main():
    ap = argparse.ArgumentParser(description="Сканер ценности по расхождению кэфов между букмекерами")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--sports", help="Список sport_key через запятую, например soccer_epl,soccer_russia_premier_league")
    src.add_argument("--all", action="store_true", help="Все активные лиги/виды спорта (~77 штук) - дорого по квоте, см. оценку перед запуском")
    ap.add_argument("--regions", default="eu", help="Регионы букмекеров (eu дешевле всего по квоте, включает Pinnacle)")
    ap.add_argument("--market", default="h2h", choices=["h2h", "totals", "spreads"])
    ap.add_argument("--min-ev", type=float, default=0.03, help="Минимальный EV для показа (0.03 = 3%%)")
    ap.add_argument("--max-odds", type=float, default=8.0, help="Макс. кэф для участия в анализе (выше - ненадёжный devig, favorite-longshot bias)")
    ap.add_argument("--max-staleness", type=float, default=600, help="Макс. расхождение времени обновления кэфов между букмекерами, сек")
    ap.add_argument("--min-books", type=int, default=2, help="Минимум независимых букмекеров, подтверждающих эдж (защита от битых/устаревших котировок)")
    ap.add_argument("--include-niche", action="store_true", help="Не фильтровать по доверию к лиге - сканировать вообще всё (раздел 3.2: зона риска)")
    ap.add_argument("--yes", action="store_true", help="Не спрашивать подтверждение при --all")
    ap.add_argument("--auto-log", action="store_true", help="Автоматически добавить все подтверждённые кандидаты в signal_log.csv как pending (для статистики - это НЕ значит 'ставить', качественная проверка отдельно)")
    ap.add_argument("--top", type=int, default=10, help="Сколько топ-кандидатов по EV выводить для дальнейшей качественной проверки")
    args = ap.parse_args()

    api_key = load_api_key()
    all_opportunities = []

    if args.all:
        sport_keys = fetch_all_active_sports(api_key)
        if not args.include_niche:
            before = len(sport_keys)
            sport_keys = [k for k in sport_keys if is_high_trust(k)]
            print(f"Фильтр доверия к лиге: {before} -> {len(sport_keys)} (раздел 3.2; "
                  f"--include-niche чтобы сканировать всё)", file=sys.stderr)
    else:
        sport_keys = [s.strip() for s in args.sports.split(",")]

    cost_per_call = len(args.regions.split(","))
    estimated_cost = len(sport_keys) * cost_per_call
    print(f"К сканированию: {len(sport_keys)} лиг/видов спорта, {cost_per_call} кредит(ов) за вызов -> "
          f"~{estimated_cost} кредитов квоты на этот запуск.", file=sys.stderr)
    if args.all and not args.yes:
        confirm = input(f"Потратить ~{estimated_cost} запросов квоты на полный обход всех видов спорта? [y/N]: ")
        if confirm.strip().lower() != "y":
            print("Отменено.")
            return

    for sport_key in sport_keys:
        try:
            events, headers = fetch_odds(api_key, sport_key, args.regions, args.market)
        except requests.HTTPError as e:
            print(f"[{sport_key}] ошибка запроса: {e}", file=sys.stderr)
            continue

        found_here = []
        for event in events:
            found_here.extend(scan_event(event, sport_key, args.market, args.min_ev, args.max_staleness, args.max_odds))
        all_opportunities.extend(found_here)

        remaining = headers.get("x-requests-remaining", "?")
        print(f"[{sport_key}] событий: {len(events)}, найдено возможностей: {len(found_here)}, "
              f"квоты осталось: {remaining}", file=sys.stderr)

    if not all_opportunities:
        print("Ничего не найдено по заданному порогу EV. Попробуйте снизить --min-ev или добавить лиги.")
        return

    # Группируем по (событие, исход): сигнал от ОДНОГО букмекера слишком часто
    # оказывается просто устаревшей/битой котировкой, а не реальным расхождением
    # рынка. Берём только случаи, где эдж подтверждён у 2+ независимых контор,
    # и для надёжности считаем EV по медианной цене среди них, а не по лучшей.
    groups: dict[tuple, list] = {}
    for o in all_opportunities:
        groups.setdefault((o["event"], o["selection"]), []).append(o)

    confirmed = []
    for (event, selection), items in groups.items():
        if len(items) < args.min_books:
            continue
        prices = sorted(x["odds"] for x in items)
        median_price = prices[len(prices) // 2]
        fair_p = items[0]["fair_prob"]
        confirmed.append(
            {
                "event": event,
                "selection": selection,
                "sport_key": items[0]["sport_key"],
                "home_team": items[0]["home_team"],
                "away_team": items[0]["away_team"],
                "market": items[0]["market"],
                "commence_time": items[0]["commence_time"],
                "n_books": len(items),
                "books": ", ".join(sorted(x["bookmaker"] for x in items)),
                "median_odds": median_price,
                "ev_median": fair_p * median_price - 1.0,
                "fair_prob": fair_p,
            }
        )

    confirmed.sort(key=lambda o: o["ev_median"], reverse=True)

    if args.auto_log:
        from signal_log import add_pending
        for o in confirmed:
            add_pending(
                date=o["commence_time"][:10],
                event=o["event"],
                market=o["market"],
                odds=o["median_odds"],
                prob=o["fair_prob"],
                sport_key=o["sport_key"],
                home_team=o["home_team"],
                away_team=o["away_team"],
                selection=o["selection"],
            )
        print(f"Залогировано {len(confirmed)} кандидатов в signal_log.csv как pending "
              f"(это для статистики/бэктеста, НЕ значит 'ставить' - качественная проверка отдельно).",
              file=sys.stderr)

    shortlist = confirmed[: args.top]
    print("=" * 110)
    print(f"{'EV(медиана)':>12} | {'Кэф':>6} | {'#БК':>3} | {'Исход':<20} | {'Событие':<40} | Начало")
    print("=" * 110)
    for o in shortlist:
        print(f"{o['ev_median']*100:>11.1f}% | {o['median_odds']:>6.2f} | {o['n_books']:>3} | "
              f"{o['selection']:<20} | {o['event']:<40} | {o['commence_time']}")
    print("=" * 110)
    print(f"Сырых сигналов (1 букмекер): {len(all_opportunities)} - шум, не показан.")
    print(f"Подтверждено {args.min_books}+ букмекерами: {len(confirmed)}, показан топ-{len(shortlist)} по EV.")
    print(f"ВАЖНО: это только количественный фильтр (расхождение кэфов). Ни одна строка здесь НЕ готовый "
          f"сигнал для ставки - по каждой нужна качественная проверка (форма/травмы/новости) прежде чем "
          f"показывать как рекомендацию пользователю.")


if __name__ == "__main__":
    main()
