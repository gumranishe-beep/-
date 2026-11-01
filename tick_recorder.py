#!/usr/bin/env python3
"""
Высокочастотный рекордер для BTC/ETH 15m+hourly Up/Down рынков Polymarket.

Зачем: вся ночь анализа историческими данными упёрлась в то, что у нас нет
потикового (посекундного) разрешения ордербука -- MarketLens даёт только
1-минутные бары, а рынок двигается на 10-30%+ ВНУТРИ минуты. Этот рекордер
пишет свой собственный потиковый архив вперёд во времени: снимки ордербука
каждые ~3 секунды + полную ленту сделок с атрибуцией кошельков, плюс отдельно
дособирает сделки известных прибыльных операторов (devonpoll, apolimatos,
brotlipolis) через их персональную историю на случай, если они торгуют
продукты, которые этот рекордер не покрывает активным мониторингом окон
(5m, 4h, ETH-hourly и т.д.).

Ничего не торгует. Чисто сбор данных для будущего анализа механики (глубина
стакана в момент их реальных решений -- та самая гипотеза, которую мы не
могли проверить из-за грубости MarketLens).
"""
import json
import time
import traceback
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
COIN_PREFIX = {"btc": "bitcoin", "eth": "ethereum"}
COINS = ["btc", "eth"]
PRODUCTS = [
    {"name": "15m", "dur": 900, "kind": "numeric"},
    {"name": "hourly", "dur": 3600, "kind": "named_hourly"},
]

KNOWN_WALLETS = {
    "devonpoll": "0x828b32d58d6624b0716f8f8661cbef5529cba12b",
    "apolimatos": "0x20c93453ab5da9386892140e83638a46b8b6e915",
    "devonpoll2": "0x7b32b6372709f19360d22271643f4e2a32a1377d",
    "brotlipolis": "0xd14b19389181e92e0024168ae741a7881d1d5896",
}

BOOK_POLL_INTERVAL = 3       # секунды между снимками ордербука активных окон
WALLET_POLL_INTERVAL = 15    # секунды между проверками персональной истории кошельков
MARKET_TRADES_POLL_INTERVAL = 5  # секунды между проверками полной ленты сделок рынка

ORDERBOOK_LOG = "recorder_orderbook.jsonl"
MARKET_TRADES_LOG = "recorder_market_trades.jsonl"
WALLET_TRADES_LOG = "recorder_wallet_trades.jsonl"
EVENTS_LOG = "recorder_events.log"


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(EVENTS_LOG, "a") as f:
        f.write(line + "\n")


def http_get_json(url, retries=3, timeout=8):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tick-recorder/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(0.3 * (attempt + 1))
    return None


def window_start(ts, dur):
    return int(ts // dur) * dur


def hourly_slug(coin, w):
    prefix = COIN_PREFIX[coin]
    dt = datetime.fromtimestamp(w, tz=ET)
    month = dt.strftime("%B").lower()
    day = dt.day
    year = dt.year
    hour12 = dt.hour % 12 or 12
    ampm = "am" if dt.hour < 12 else "pm"
    return f"{prefix}-up-or-down-{month}-{day}-{year}-{hour12}{ampm}-et"


def fetch_event(coin, product, w):
    if product["kind"] == "numeric":
        slug = f"{coin}-updown-{product['name']}-{w}"
    else:
        slug = hourly_slug(coin, w)
    data = http_get_json(f"https://gamma-api.polymarket.com/events?slug={slug}")
    if not data or not isinstance(data, list) or not data:
        return None
    return data[0]


def fetch_book(token_id):
    return http_get_json(f"https://clob.polymarket.com/book?token_id={token_id}")


def fetch_market_trades(cond_id, limit=200):
    data = http_get_json(f"https://data-api.polymarket.com/trades?market={cond_id}&limit={limit}")
    return data or []


def fetch_wallet_trades(wallet, limit=100):
    data = http_get_json(f"https://data-api.polymarket.com/trades?user={wallet}&limit={limit}")
    return data or []


def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


def main():
    log(f"Старт tick-рекордера. Продукты: {[p['name'] for p in PRODUCTS]}, монеты: {COINS}, "
        f"отслеживаемые кошельки: {list(KNOWN_WALLETS.keys())}")

    # кэш: ключ трека -> {"up_token_id", "cond"}
    track_tokens = {}
    # дедупликация сделок рынка: ключ трека -> set транзакций (ts,price,size,side,wallet)
    seen_market_trades = {}
    # дедупликация сделок кошельков: wallet -> set
    seen_wallet_trades = {name: set() for name in KNOWN_WALLETS}

    last_book_poll = 0
    last_market_trades_poll = 0
    last_wallet_poll = 0

    while True:
        try:
            now = time.time()

            # --- снимки ордербука активных окон ---
            if now - last_book_poll >= BOOK_POLL_INTERVAL:
                last_book_poll = now
                for coin in COINS:
                    for product in PRODUCTS:
                        dur = product["dur"]
                        w = window_start(now, dur)
                        key = f"{coin}-{product['name']}-{w}"

                        if key not in track_tokens:
                            ev = fetch_event(coin, product, w)
                            if not ev or not ev.get("markets"):
                                continue
                            m = ev["markets"][0]
                            try:
                                clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                                up_token_id = clob_ids[0]
                            except Exception:
                                continue
                            track_tokens[key] = {"up_token_id": up_token_id, "cond": m.get("conditionId")}

                        info = track_tokens.get(key)
                        if not info or not info.get("up_token_id"):
                            continue

                        book = fetch_book(info["up_token_id"])
                        if book:
                            append_jsonl(ORDERBOOK_LOG, {
                                "ts": now, "coin": coin, "product": product["name"], "w": w,
                                "cond": info["cond"],
                                "bids": book.get("bids", []), "asks": book.get("asks", []),
                                "last_trade_price": book.get("last_trade_price"),
                            })

            # --- полная лента сделок активных окон (с дедупликацией) ---
            if now - last_market_trades_poll >= MARKET_TRADES_POLL_INTERVAL:
                last_market_trades_poll = now
                for key, info in list(track_tokens.items()):
                    cond = info.get("cond")
                    if not cond:
                        continue
                    trades = fetch_market_trades(cond)
                    if not trades:
                        continue
                    seen = seen_market_trades.setdefault(key, set())
                    new_trades = []
                    for t in trades:
                        sig = (t.get("timestamp"), t.get("price"), t.get("size"),
                               t.get("side"), t.get("proxyWallet"))
                        if sig in seen:
                            continue
                        seen.add(sig)
                        new_trades.append(t)
                    if new_trades:
                        append_jsonl(MARKET_TRADES_LOG, {
                            "ts_collected": now, "key": key, "cond": cond, "trades": new_trades,
                        })

            # --- персональная история известных кошельков ---
            if now - last_wallet_poll >= WALLET_POLL_INTERVAL:
                last_wallet_poll = now
                for name, wallet in KNOWN_WALLETS.items():
                    trades = fetch_wallet_trades(wallet)
                    if not trades:
                        continue
                    seen = seen_wallet_trades[name]
                    new_trades = []
                    for t in trades:
                        sig = (t.get("timestamp"), t.get("price"), t.get("size"),
                               t.get("side"), t.get("conditionId"))
                        if sig in seen:
                            continue
                        seen.add(sig)
                        new_trades.append(t)
                    if new_trades:
                        append_jsonl(WALLET_TRADES_LOG, {
                            "ts_collected": now, "wallet_name": name, "wallet": wallet,
                            "trades": new_trades,
                        })
                        log(f"новых сделок у {name}: {len(new_trades)}")

            # периодическая чистка старых track_tokens (окна давно закрылись)
            if int(now) % 300 < 1:
                cutoff = now - 2 * 3600
                stale = [k for k, info in track_tokens.items()
                         if int(k.rsplit("-", 1)[-1]) < cutoff]
                for k in stale:
                    track_tokens.pop(k, None)
                    seen_market_trades.pop(k, None)

        except Exception:
            log("ОШИБКА в главном цикле:\n" + traceback.format_exc())

        time.sleep(1)


if __name__ == "__main__":
    main()
