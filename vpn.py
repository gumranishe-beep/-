from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db, User, Device, Server
from app.api.users import get_current_user
from app.core.config import settings

router = APIRouter()


@router.get("/servers")
async def get_servers(db: Session = Depends(get_db)):
    """Список доступных VPN-серверов"""
    servers = db.query(Server).filter(Server.is_active == True).all()

    return {
        "servers": [
            {
                "code": s.code,
                "name": s.name,
                "country": s.country,
                "flag": get_flag(s.code),
                "ping": get_ping(s.code),
                "load": s.load_percent
            }
            for s in servers
        ]
    }


@router.post("/connect/{server_code}")
async def connect_vpn(
    server_code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Подключение к VPN-серверу"""
    server = db.query(Server).filter(Server.code == server_code, Server.is_active == True).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Проверка лимита устройств
    device_count = db.query(Device).filter(Device.user_id == user.telegram_id).count()
    if device_count >= user.device_limit:
        raise HTTPException(status_code=403, detail="Device limit reached")

    # Генерация WireGuard конфигурации
    config = generate_wireguard_config(user, server)

    # Сохранение
    user.vpn_config = config
    user.vpn_server = server_code
    user.vpn_connected_at = datetime.utcnow()

    # Добавление устройства
    device = Device(
        user_id=user.telegram_id,
        name=f"{server.name} VPN",
        device_type="phone",
        public_key=config.get('public_key')
    )
    db.add(device)
    db.commit()

    return {
        "status": "connected",
        "server": {
            "code": server.code,
            "name": server.name,
            "endpoint": server.endpoint
        },
        "config": config
    }


@router.post("/disconnect")
async def disconnect_vpn(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Отключение от VPN"""
    user.vpn_config = None
    user.vpn_server = None
    user.vpn_connected_at = None
    db.commit()

    return {"status": "disconnected"}


def get_flag(code: str) -> str:
    flags = {
        'ru': '🇷🇺', 'de': '🇩🇪', 'nl': '🇳🇱',
        'us': '🇺🇸', 'sg': '🇸🇬', 'fr': '🇫🇷',
        'gb': '🇬🇧', 'jp': '🇯🇵', 'kr': '🇰🇷'
    }
    return flags.get(code, '🌍')


def get_ping(code: str) -> int:
    # В реальности - измерение пинга
    pings = {
        'ru': 12, 'de': 45, 'nl': 38,
        'us': 120, 'sg': 89, 'fr': 50
    }
    return pings.get(code, 100)


def generate_wireguard_config(user: User, server: Server) -> dict:
    """Генерация WireGuard конфигурации"""
    import secrets

    private_key = secrets.token_hex(32)
    public_key = secrets.token_hex(32)

    return {
        "private_key": private_key,
        "public_key": public_key,
        "address": f"10.0.0.{user.id % 254 + 1}/24",
        "dns": settings.VPN_DNS,
        "endpoint": f"{server.endpoint}:{server.port}",
        "allowed_ips": "0.0.0.0/0, ::/0",
        "persistent_keepalive": 25
    }
