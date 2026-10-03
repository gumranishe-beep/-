#!/usr/bin/env python3
"""
Калибровочная модель поверх наших оценок вероятности (Platt scaling).

Это НЕ модель, которая предсказывает исход матча с нуля - для этого нет
ни данных, ни фич. Это узкая, честная задача: у нас уже есть вероятность
(fair_prob из devig, либо ручная оценка) и фактический исход по каждому
закрытому сигналу. Модель учится поправлять систематическое смещение
в этой вероятности (например, если наш метод в среднем завышает шансы
дальних андердогов). Один вход (наша вероятность), один выход (исправленная).

Жёсткие правила, чтобы не наврать самим себе на маленькой выборке:
- не обучаемся вообще ниже MIN_TOTAL записей
- разбивка train/test ТОЛЬКО по времени (сначала хронологически более ранние
  в train, более поздние в test) - рандомный сплит на ставках даёт утечку,
  рынок и наша методология дрейфуют во времени
- новая модель принимается, только если она ЛУЧШЕ бейзлайна (использование
  сырой вероятности без калибровки) на отложенной выборке по log-loss,
  причём с запасом - иначе случайное улучшение на шуме примем за сигнал
- если условия не выполнены - используем сырую вероятность без калибровки,
  это явно логируется, а не скрывается
"""

import json
import os
import pickle
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from signal_log import _load_rows  # noqa: E402

MIN_TOTAL = 100          # меньше этого - даже не пытаемся обучать
MIN_TEST = 20            # размер отложенной выборки для честной оценки
MIN_IMPROVEMENT = 0.02   # требуем relative improvement >=2% по log-loss, не просто "чуть лучше"

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
METADATA_PATH = os.path.join(os.path.dirname(__file__), "metadata.json")
TRAINING_LOG_PATH = os.path.join(os.path.dirname(__file__), "training_log.csv")


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def load_settled_sorted() -> list[dict]:
    rows = [r for r in _load_rows() if r["status"] == "settled" and r["prob"] and r["result"] != ""]
    rows.sort(key=lambda r: r["date"])
    return rows


def _log_attempt(status: str, n_total: int, extra: str = ""):
    header_needed = not os.path.exists(TRAINING_LOG_PATH)
    with open(TRAINING_LOG_PATH, "a", encoding="utf-8") as f:
        if header_needed:
            f.write("timestamp,status,n_total,details\n")
        ts = datetime.now(timezone.utc).isoformat()
        f.write(f"{ts},{status},{n_total},\"{extra}\"\n")


def train_and_maybe_promote() -> dict:
    rows = load_settled_sorted()
    n_total = len(rows)

    if n_total < MIN_TOTAL:
        msg = f"Недостаточно данных: {n_total}/{MIN_TOTAL} закрытых сигналов. Калибровка не запускается."
        _log_attempt("skipped_not_enough_data", n_total, msg)
        return {"status": "skipped", "reason": msg, "n_total": n_total}

    split_idx = int(n_total * 0.8)
    n_test = n_total - split_idx
    if n_test < MIN_TEST:
        split_idx = n_total - MIN_TEST
        n_test = MIN_TEST

    train_rows, test_rows = rows[:split_idx], rows[split_idx:]

    X_train = _logit(np.array([float(r["prob"]) for r in train_rows])).reshape(-1, 1)
    y_train = np.array([int(r["result"]) for r in train_rows])
    X_test = _logit(np.array([float(r["prob"]) for r in test_rows])).reshape(-1, 1)
    y_test = np.array([int(r["result"]) for r in test_rows])
    raw_prob_test = np.array([float(r["prob"]) for r in test_rows])

    if len(set(y_train)) < 2:
        msg = "В train-выборке только один класс исходов (все win или все loss) - обучать нечего."
        _log_attempt("skipped_single_class", n_total, msg)
        return {"status": "skipped", "reason": msg, "n_total": n_total}

    model = LogisticRegression()
    model.fit(X_train, y_train)
    calibrated_prob_test = model.predict_proba(X_test)[:, 1]

    baseline_logloss = log_loss(y_test, raw_prob_test, labels=[0, 1])
    calibrated_logloss = log_loss(y_test, calibrated_prob_test, labels=[0, 1])
    baseline_brier = brier_score_loss(y_test, raw_prob_test)
    calibrated_brier = brier_score_loss(y_test, calibrated_prob_test)

    relative_improvement = (baseline_logloss - calibrated_logloss) / baseline_logloss

    result = {
        "status": None,
        "n_total": n_total,
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "baseline_logloss": round(baseline_logloss, 4),
        "calibrated_logloss": round(calibrated_logloss, 4),
        "baseline_brier": round(baseline_brier, 4),
        "calibrated_brier": round(calibrated_brier, 4),
        "relative_improvement": round(relative_improvement, 4),
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    if relative_improvement >= MIN_IMPROVEMENT:
        # Принимаем: переобучаем на ВСЕХ данных (train+test) для деплоя,
        # но решение "принять или нет" основано только на честном holdout выше.
        X_all = _logit(np.array([float(r["prob"]) for r in rows])).reshape(-1, 1)
        y_all = np.array([int(r["result"]) for r in rows])
        final_model = LogisticRegression()
        final_model.fit(X_all, y_all)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(final_model, f)
        result["status"] = "accepted"
        with open(METADATA_PATH, "w") as f:
            json.dump(result, f, indent=2)
        _log_attempt("accepted", n_total, f"improvement={relative_improvement:.1%}")
    else:
        result["status"] = "rejected"
        _log_attempt("rejected", n_total,
                     f"improvement={relative_improvement:.1%} < требуемых {MIN_IMPROVEMENT:.0%}")

    return result


def get_calibrated_prob(raw_prob: float) -> float:
    """Используется пайплайном (value_scanner.py). Если принятой модели нет -
    честно возвращает сырую вероятность без изменений (identity fallback)."""
    if not os.path.exists(MODEL_PATH) or not os.path.exists(METADATA_PATH):
        return raw_prob
    with open(METADATA_PATH) as f:
        meta = json.load(f)
    if meta.get("status") != "accepted":
        return raw_prob
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    x = _logit(np.array([raw_prob])).reshape(-1, 1)
    return float(model.predict_proba(x)[0, 1])


def is_calibration_active() -> bool:
    if not os.path.exists(METADATA_PATH):
        return False
    with open(METADATA_PATH) as f:
        return json.load(f).get("status") == "accepted"


def main():
    result = train_and_maybe_promote()
    if result["status"] == "skipped":
        print(result["reason"])
        return
    print(f"Всего закрытых сигналов: {result['n_total']} (train={result['n_train']}, test={result['n_test']})")
    print(f"Log-loss на отложенной выборке: baseline={result['baseline_logloss']}, "
          f"калиброванная={result['calibrated_logloss']} ({result['relative_improvement']:+.1%})")
    print(f"Brier score: baseline={result['baseline_brier']}, калиброванная={result['calibrated_brier']}")
    if result["status"] == "accepted":
        print(f"ПРИНЯТО: калибровочная модель сохранена, улучшение {result['relative_improvement']:.1%} "
              f">= порога {MIN_IMPROVEMENT:.0%}. Будет использоваться в value_scanner.py.")
    else:
        print(f"ОТКЛОНЕНО: улучшение {result['relative_improvement']:.1%} меньше порога "
              f"{MIN_IMPROVEMENT:.0%} - используем сырую вероятность, модель не заменена.")


if __name__ == "__main__":
    main()
