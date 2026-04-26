from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.core.database import get_db, User
from app.core.security import validate_telegram_init_data

router = APIRouter()


@router.post("/login")
async def login(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: Session = Depends(get_db)
):
    """Авторизация через Telegram Web App"""
    user_data = validate_telegram_init_data(x_telegram_init_data)

    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid Telegram data")

    telegram_id = user_data.get('id')

    # Поиск или создание пользователя
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        user = User(
            telegram_id=telegram_id,
            username=user_data.get('username'),
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            photo_url=user_data.get('photo_url')
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "user": {
            "id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "photo_url": user.photo_url
        },
        "subscription": {
            "traffic_used": user.traffic_used_gb,
            "traffic_limit": user.traffic_limit_gb,
            "device_limit": user.device_limit,
            "is_active": user.vpn_config is not None
        }
    }
