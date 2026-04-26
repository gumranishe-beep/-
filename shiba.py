from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db, User, DailyQuest
from app.api.users import get_current_user
from app.core.config import settings

router = APIRouter()


@router.get("/status")
async def get_shiba_status(user: User = Depends(get_current_user)):
    """Статус Шибы"""
    hunger = user.shiba_hunger

    # Уменьшение голода со временем
    if user.shiba_last_fed:
        hours_since = (datetime.utcnow() - user.shiba_last_fed).total_seconds() / 3600
        hunger = max(0, 100 - int(hours_since * 5))  # -5% в час

    mood = "happy" if hunger > 70 else "normal" if hunger > 30 else "sad"

    return {
        "mood": mood,
        "hunger": hunger,
        "last_fed": user.shiba_last_fed.isoformat() if user.shiba_last_fed else None,
        "can_feed": user.shiba_last_fed is None or 
                    (datetime.utcnow() - user.shiba_last_fed) > timedelta(hours=4),
        "message": get_shiba_message(mood)
    }


@router.post("/feed")
async def feed_shiba(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Накормить Шибу"""
    # Проверка cooldown
    if user.shiba_last_fed and (datetime.utcnow() - user.shiba_last_fed) < timedelta(hours=4):
        hours_left = 4 - (datetime.utcnow() - user.shiba_last_fed).total_seconds() / 3600
        return {
            "error": "Too soon",
            "hours_left": round(hours_left, 1)
        }

    # Обновление состояния Шибы
    user.shiba_last_fed = datetime.utcnow()
    user.shiba_hunger = 100
    user.shiba_mood = "happy"

    # Бонус трафика
    user.traffic_used_gb = max(0, user.traffic_used_gb - 0.1)

    # Ежедневный квест
    today = datetime.utcnow().date()
    quest = db.query(DailyQuest).filter(
        DailyQuest.user_id == user.telegram_id,
        DailyQuest.quest_type == "feed",
        func.date(DailyQuest.quest_date) == today
    ).first()

    if not quest:
        quest = DailyQuest(
            user_id=user.telegram_id,
            quest_date=datetime.utcnow(),
            quest_type="feed",
            completed=True,
            reward_mb=settings.DAILY_FEED_BONUS_MB
        )
        db.add(quest)
        user.traffic_limit_gb += settings.DAILY_FEED_BONUS_MB / 1024

    db.commit()

    return {
        "status": "fed",
        "hunger": 100,
        "mood": "happy",
        "bonus_traffic_mb": settings.DAILY_FEED_BONUS_MB,
        "message": "Ням-ням! Шиба счастлива! 🍖🐕"
    }


@router.get("/daily-quests")
async def get_daily_quests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ежедневные квесты"""
    today = datetime.utcnow().date()

    quests = db.query(DailyQuest).filter(
        DailyQuest.user_id == user.telegram_id,
        func.date(DailyQuest.quest_date) == today
    ).all()

    quest_types = ["feed", "connect", "share"]
    completed = {q.quest_type: q.completed for q in quests}

    return {
        "quests": [
            {
                "type": qt,
                "title": get_quest_title(qt),
                "completed": completed.get(qt, False),
                "reward_mb": 100 if qt == "feed" else 200 if qt == "connect" else 300
            }
            for qt in quest_types
        ]
    }


def get_shiba_message(mood: str) -> str:
    messages = {
        "happy": ["Гав-гав! Я такая счастливая! 🥰", "Лучший друг! 🐕", "VPN работает отлично! 🛡️"],
        "normal": ["Привет! Как дела? 😊", "Я готова к работе! 💪", "Подключи VPN? 🌐"],
        "sad": ["Я проголодалась... 🥺", "Накорми меня? 🍖", "Мне грустно без еды... 😢"]
    }
    import random
    return random.choice(messages.get(mood, ["Гав! 🐕"]))


def get_quest_title(quest_type: str) -> str:
    titles = {
        "feed": "Накормить Шибу",
        "connect": "Подключить VPN",
        "share": "Поделиться с другом"
    }
    return titles.get(quest_type, "Квест")
