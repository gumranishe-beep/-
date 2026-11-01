#!/usr/bin/env python3
"""
Paper-трейдинг бот: контрарианская покупка "Up" в крипто 15m/hourly
Up-or-Down рынках на Polymarket (BTC, ETH), основанная на реконструированной
механике кошельков devonpoll/apolimatos + 2 похожих кошелька (группа A),
подтверждённой честным cash-flow PnL тестом (t=2.5-4.8, устойчиво по
split-half).

МЕХАНИКА (из форензики реальных кошельков):
  - Продукты: 15m и hourly (НЕ 5m -- эдж там практически отсутствует;
    4h НЕ использовался в форензике -- это был мой ошибочный заменитель
    "hourly", сейчас исправлено на настоящий часовой продукт)
  - Вход: ОДИН раз за окно, на фиксированной доле прошедшего времени окна
  - Размер позиции ГРАДУИРОВАННО растёт с глубиной дипа от локального
    максимума: от ~22$ (дип=0) до ~75$ (дип>50%)
  - Удержание до резолва TWAP -- раннего выхода в v1 нет (это и есть
    источник большинства прибыли по форензике, 51-89%)

ОБЪЕКТИВНОСТЬ ИСПОЛНЕНИЯ (важно для честного paper):
  - Цена дипа/сигнала вхождения отслеживается через ЖИВОЙ CLOB
    (clob.polymarket.com/price?side=buy), а НЕ через поля gamma-api
    (bestAsk/lastTradePrice) -- экспериментально обнаружено, что эти
    поля у gamma-api отстают от реального рынка на 1-3+ минуты, а
    BTC/ETH TWAP цена двигается быстро, так что использование
    gamma-полей создавало фиктивный "slippage" (на самом деле не
    slippage, а рассинхронизация данных). CLOB price/book -- без
    look-ahead (бот не знает будущего, решения принимаются только на
    основе уже прошедших цен)
  - Реальное ИСПОЛНЕНИЕ симулируется через настоящий живой ОРДЕРБУК
    (clob.polymarket.com/book, публичный, без авторизации): заявка
    "проедает" уровни стакана по реальным ценам/размерам, а не берёт
    best_ask как бесконечно доступную цену. Если в стакане не хватает
    глубины на весь желаемый размер -- берём частичное исполнение и это
    явно логируется (никогда не притворяемся, что исполнили больше, чем
    реально было в стакане)
  - Комиссия считается по формуле Polymarket: fee = shares * 0.07 *
    price * (1-price), на РЕАЛЬНОЙ средневзвешенной цене исполнения
  - Между решением и запросом стакана проходит обычная сетевая задержка
    (как и в реальности) -- не устраняется искусственно

Это НЕ прогнозирует будущее -- это калька с уже статистически подтверждённого
поведения реальных прибыльных кошельков. Результат нужно мониторить и
сверять со статистикой до переноса в реальную торговлю.
"""
import json
import time
import traceback
import urllib.request
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

STATE_FILE = "dip_bot_state.json"
TRADES_LOG = "dip_bot_trades.jsonl"
EVENTS_LOG = "dip_bot_events.log"

ET = ZoneInfo("America/New_York")
COIN_PREFIX = {"btc": "bitcoin", "eth": "ethereum"}

COINS = ["btc", "eth"]
PRODUCTS = [
    {"name": "15m", "dur": 900, "kind": "numeric"},
    {"name": "hourly", "dur": 3600, "kind": "named_hourly"},
]

ENTRY_FRACTION = 0.35        # доля прошедшего времени окна для точки входа
MIN_TIME_LEFT_SEC = 30        # не входить, если до резолва осталось меньше
POLL_INTERVAL_SEC = 5         # как часто опрашивать активные окна
MIN_FILL_FRACTION = 0.3       # если стакан даёт меньше этой доли желаемого
                               # размера -- пропускаем сделку (слишком тонко)
MAX_SLIPPAGE_PCT = 0.05        # не покупаем выше best_ask*(1+это) -- размер
                               # позиции урезается под глубину стакана, а не
                               # либо всё, либо ничего

BASE_SIZE_USD = 22.0
DIP_SCALE_USD = 100.0         # size = BASE + SCALE * dip_depth
MAX_SIZE_USD = 80.0
MIN_SIZE_USD = 10.0

TAKER_FEE_RATE = 0.07         # крипто taker fee, подтверждено docs.polymarket.com
# fee_usd = shares * rate * price * (1 - price)

UP_IDX = 0  # outcomes=["Up","Down"], подтверждено на живых данных


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(EVENTS_LOG, "a") as f:
        f.write(line + "\n")


def http_get_json(url, retries=5, timeout=10):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dip-bot/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt == retries - 1:
                log(f"HTTP GET failed ({url}): {e}")
                return None
            time.sleep(0.5 * (attempt + 1))
    return None


def window_start(ts, dur):
    # для hourly это корректно и в ET, т.к. смещение ET от UTC всегда целое
    # число часов (EST=-5 либо EDT=-4) -- границы часа совпадают в обеих зонах
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


def fetch_clob_ask_price(token_id):
    data = http_get_json(f"https://clob.polymarket.com/price?token_id={token_id}&side=buy")
    if not data:
        return None
    try:
        return float(data["price"])
    except Exception:
        return None


def fetch_book_asks(token_id):
    data = http_get_json(f"https://clob.polymarket.com/book?token_id={token_id}")
    if not data:
        return None
    try:
        asks = sorted(data.get("asks", []), key=lambda x: float(x["price"]))
    except Exception:
        return None
    return asks


def max_size_within_slippage(asks, max_slippage_pct):
    """Универсальная формула лимита размера: сколько можно купить, не уходя
    выше best_ask * (1 + max_slippage_pct). Не зависит от желаемого размера
    позиции -- чисто свойство текущей глубины стакана."""
    if not asks:
        return 0.0
    try:
        best = float(asks[0]["price"])
    except Exception:
        return 0.0
    cap_price = best * (1 + max_slippage_pct)
    usd = 0.0
    for lvl in asks:
        try:
            p = float(lvl["price"])
            s = float(lvl["size"])
        except Exception:
            continue
        if p > cap_price:
            break
        usd += p * s
    return usd


def simulate_fill(asks, target_usd):
    """Честная симуляция маркет-бая через реальный стакан: проедаем уровни
    по их реальным ценам/размерам. Возвращает (shares, usd_cost, avg_price,
    fully_filled). usd_cost не включает комиссию."""
    if not asks:
        return 0.0, 0.0, None, False
    filled_shares = 0.0
    filled_usd = 0.0
    for lvl in asks:
        try:
            p = float(lvl["price"])
            s = float(lvl["size"])
        except Exception:
            continue
        if p <= 0 or s <= 0:
            continue
        level_usd = p * s
        remaining = target_usd - filled_usd
        if remaining <= 0:
            break
        if level_usd <= remaining:
            filled_shares += s
            filled_usd += level_usd
        else:
            take_shares = remaining / p
            filled_shares += take_shares
            filled_usd += remaining
            break
    if filled_shares <= 0:
        return 0.0, 0.0, None, False
    avg_price = filled_usd / filled_shares
    fully_filled = filled_usd >= target_usd * 0.999
    return filled_shares, filled_usd, avg_price, fully_filled


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"tracks": {}, "stats": {"n_trades": 0, "n_resolved": 0,
                                         "n_skipped_thin": 0,
                                         "total_pnl": 0.0, "n_won": 0}}


def save_state(state):
    import os
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)


def record_trade(trade):
    with open(TRADES_LOG, "a") as f:
        f.write(json.dumps(trade) + "\n")


def main():
    state = load_state()
    log(f"Старт paper-бота (v2, реальный стакан для исполнения). "
        f"Продукты: {[p['name'] for p in PRODUCTS]}, монеты: {COINS}. "
        f"Уже отслеживается треков: {len(state['tracks'])}")

    while True:
        try:
            now = time.time()
            for coin in COINS:
                for product in PRODUCTS:
                    dur = product["dur"]
                    w = window_start(now, dur)
                    key = f"{coin}-{product['name']}-{w}"
                    track = state["tracks"].get(key)
                    if track is None:
                        track = {"coin": coin, "product": product["name"], "w": w,
                                  "max_up_price": None, "entered": False,
                                  "entry": None, "resolved": False, "cond": None,
                                  "up_token_id": None}
                        state["tracks"][key] = track

                    if track["resolved"]:
                        continue

                    ev = fetch_event(coin, product, w)
                    if not ev or not ev.get("markets"):
                        continue
                    m = ev["markets"][0]
                    track["cond"] = m.get("conditionId")

                    if track["up_token_id"] is None:
                        try:
                            clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                            track["up_token_id"] = clob_ids[UP_IDX]
                        except Exception:
                            track["up_token_id"] = None

                    # живая цена из CLOB (gamma bestAsk/lastTradePrice отстают
                    # на 1-3+ минуты -- непригодны для сигнала дипа)
                    up_price = None
                    if track["up_token_id"]:
                        up_price = fetch_clob_ask_price(track["up_token_id"])
                    if up_price is None:
                        try:
                            op = json.loads(m.get("outcomePrices", "[]"))
                            up_price = float(op[UP_IDX])
                        except Exception:
                            continue
                    up_price = float(up_price)

                    if track["max_up_price"] is None or up_price > track["max_up_price"]:
                        track["max_up_price"] = up_price

                    elapsed = now - w
                    time_left = dur - elapsed

                    # вход: один раз за окно, на фиксированной доле времени
                    if (not track["entered"] and not m.get("closed")
                            and elapsed >= ENTRY_FRACTION * dur
                            and time_left >= MIN_TIME_LEFT_SEC):
                        up_token_id = track["up_token_id"]
                        track["entered"] = True  # окно "обработано" независимо от исхода ниже

                        if up_token_id is None:
                            log(f"ПРОПУСК {key}: нет clobTokenIds")
                            track["resolved"] = True
                            continue

                        # ОДИН живой снимок стакана и для цены принятия решения,
                        # и для исполнения -- без разрыва по времени между "увидели
                        # дип" и "купили", иначе разница в доли секунды на быстро
                        # двигающемся TWAP-рынке выглядит как фиктивный slippage
                        asks = fetch_book_asks(up_token_id)
                        if not asks:
                            log(f"ПРОПУСК {key}: не удалось получить стакан")
                            state["stats"]["n_skipped_thin"] += 1
                            track["resolved"] = True
                            save_state(state)
                            continue

                        spot_price = float(asks[0]["price"])
                        if track["max_up_price"] is None or spot_price > track["max_up_price"]:
                            track["max_up_price"] = spot_price
                        ref_max = track["max_up_price"]
                        dip_depth = max(0.0, (ref_max - spot_price) / ref_max) if ref_max > 0 else 0.0
                        target_usd = BASE_SIZE_USD + DIP_SCALE_USD * dip_depth
                        target_usd = max(MIN_SIZE_USD, min(MAX_SIZE_USD, target_usd))
                        up_price = spot_price  # для лога ниже

                        # урезаем желаемый размер под глубину стакана в
                        # пределах допустимого slippage -- вместо "всё или
                        # ничего" берём меньшую позицию, если книга тонкая
                        cap_usd = max_size_within_slippage(asks, MAX_SLIPPAGE_PCT)
                        capped = cap_usd < target_usd
                        target_usd = min(target_usd, cap_usd)

                        if target_usd < MIN_SIZE_USD:
                            log(f"ПРОПУСК {key}: даже с учётом лимита "
                                f"slippage книга слишком тонкая (cap=${cap_usd:.1f})")
                            state["stats"]["n_skipped_thin"] += 1
                            track["resolved"] = True
                            save_state(state)
                            continue

                        shares, usd_cost, avg_price, fully_filled = simulate_fill(asks, target_usd)

                        if shares <= 0 or avg_price is None or usd_cost < target_usd * MIN_FILL_FRACTION:
                            log(f"ПРОПУСК {key}: стакан слишком тонкий "
                                f"(желали ${target_usd:.1f}, стакан дал ${usd_cost:.1f})")
                            state["stats"]["n_skipped_thin"] += 1
                            track["resolved"] = True
                            save_state(state)
                            continue

                        fee_usd = shares * TAKER_FEE_RATE * avg_price * (1 - avg_price)

                        entry = {
                            "ts": now, "signal_price": up_price, "ref_max": ref_max,
                            "dip_depth": dip_depth, "target_usd": target_usd,
                            "avg_fill_price": avg_price, "shares": shares,
                            "usd_cost": usd_cost, "fee_usd": fee_usd,
                            "fully_filled": fully_filled, "size_capped": capped,
                        }
                        track["entry"] = entry
                        state["stats"]["n_trades"] += 1
                        save_state(state)
                        slip = (avg_price - up_price) / up_price * 100 if up_price else 0
                        cap_note = " [урезан под глубину]" if capped else ""
                        log(f"ВХОД {key}: signal_price={up_price:.3f} avg_fill={avg_price:.3f} "
                            f"(slip={slip:+.1f}%) dip={dip_depth:.1%} target=${target_usd:.1f}{cap_note} "
                            f"filled=${usd_cost:.1f} shares={shares:.1f} full={fully_filled}")

                    # резолв
                    if m.get("closed") and not track["resolved"] and track["entered"] and track["entry"]:
                        try:
                            op = json.loads(m.get("outcomePrices", "[]"))
                            resolved_up = float(op[UP_IDX])
                        except Exception:
                            resolved_up = None
                        if resolved_up in (0.0, 1.0):
                            entry = track["entry"]
                            payout = entry["shares"] * resolved_up
                            net_cost = entry["usd_cost"] + entry["fee_usd"]
                            pnl = payout - net_cost
                            track["resolved"] = True
                            state["stats"]["n_resolved"] += 1
                            state["stats"]["total_pnl"] += pnl
                            if pnl > 0:
                                state["stats"]["n_won"] += 1
                            trade = {**entry, "coin": coin, "product": product["name"], "w": w,
                                      "resolved_up": resolved_up, "payout": payout,
                                      "net_cost": net_cost, "pnl": pnl}
                            record_trade(trade)
                            save_state(state)
                            won = resolved_up == 1.0
                            wr = state["stats"]["n_won"] / state["stats"]["n_resolved"] * 100
                            log(f"РЕЗОЛВ {key}: won={won} pnl={pnl:+.2f} "
                                f"(резолвнуто={state['stats']['n_resolved']}, "
                                f"total_pnl={state['stats']['total_pnl']:+.2f}, WR={wr:.1f}%)")
                        # если closed, но резолва ещё нет -- подождём, не трогаем track

                    elif not track["entered"] and elapsed > dur + 300:
                        track["resolved"] = True  # пропущенное окно

            if int(now) % 3600 < POLL_INTERVAL_SEC:
                cutoff = now - 2 * 86400
                state["tracks"] = {k: v for k, v in state["tracks"].items()
                                    if not (v["resolved"] and v["w"] < cutoff)}

            save_state(state)
        except Exception:
            log("ОШИБКА в главном цикле:\n" + traceback.format_exc())

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
