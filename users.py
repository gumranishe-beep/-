from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.core.database import get_db, User, Device
from app.core.security import validate_telegram_init_data

router = APIRouter()


def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: Session = Depends(get_db)
) -> User:
    user_data = validate_telegram_init_data(x_telegram_init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == user_data['id']).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    devices = db.query(Device).filter(Device.user_id == user.telegram_id).all()

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
            "is_active": user.vpn_config is not None,
            "server": user.vpn_server
        },
        "devices": [
            {
                "id": d.id,
                "name": d.name,
                "type": d.device_type,
                "status": "active" if d.is_active else "inactive"
            }
            for d in devices
        ],
        "shiba": {
            "mood": user.shiba_mood,
            "hunger": user.shiba_hunger,
            "last_fed": user.shiba_last_fed.isoformat() if user.shiba_last_fed else None
        }
    }


@router.get("/devices")
async def get_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    devices = db.query(Device).filter(Device.user_id == user.telegram_id).all()
    return {
        "devices": [
            {
                "id": d.id,
                "name": d.name,
                "type": d.device_type,
                "status": "active" if d.is_active else "inactive",
                "last_seen": d.last_seen.isoformat() if d.last_seen else None
            }
            for d in devices
        ],
        "limit": user.device_limit
    }


@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.user_id == user.telegram_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    db.delete(device)
    db.commit()

    return {"status": "deleted"}
