from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, User, Server
from app.core.config import settings

router = APIRouter()

# Простая проверка админа (в проде - нормальная авторизация)
ADMIN_IDS = [123456789]  # Заменить на реальные ID


def check_admin(telegram_id: int):
    if telegram_id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Статистика сервиса"""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.vpn_config.isnot(None)).count()
    total_devices = db.query(Server).count()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_devices": total_devices,
        "servers": db.query(Server).count()
    }


@router.post("/servers")
async def add_server(
    code: str,
    name: str,
    country: str,
    endpoint: str,
    port: int = 51820,
    db: Session = Depends(get_db)
):
    """Добавить VPN-сервер"""
    server = Server(
        code=code,
        name=name,
        country=country,
        endpoint=endpoint,
        port=port
    )
    db.add(server)
    db.commit()

    return {"status": "created", "server_id": server.id}


@router.get("/users")
async def list_users(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    """Список пользователей"""
    users = db.query(User).offset(offset).limit(limit).all()
    return {
        "users": [
            {
                "id": u.telegram_id,
                "username": u.username,
                "traffic_used": u.traffic_used_gb,
                "referrals": u.referral_count
            }
            for u in users
        ]
    }
