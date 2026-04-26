from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db, User, ReferralLog
from app.api.users import get_current_user
from app.core.config import settings

router = APIRouter()


@router.get("/info")
async def get_referral_info(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Информация о реферальной программе"""
    referrals = db.query(ReferralLog).filter(ReferralLog.referrer_id == user.telegram_id).all()

    return {
        "referral_link": f"https://t.me/ShibaVPNBot?start=ref_{user.telegram_id}",
        "total_referrals": len(referrals),
        "active_referrals": sum(1 for r in referrals if r.is_active),
        "rewards": {
            "1": {"type": "device", "value": 1, "description": "+1 устройство"},
            "5": {"type": "traffic", "value": 0.5, "description": "+500 МБ"},
            "15": {"type": "traffic", "value": 2.0, "description": "+2 ГБ"},
            "30": {"type": "traffic", "value": 5.0, "description": "+5 ГБ"},
            "50": {"type": "vip", "value": True, "description": "VIP статус"},
            "100": {"type": "unlimited", "value": True, "description": "Безлимит"}
        },
        "my_referrals": [
            {
                "id": r.referred_id,
                "is_active": r.is_active,
                "date": r.created_at.isoformat()
            }
            for r in referrals
        ]
    }


@router.get("/rating")
async def get_rating(db: Session = Depends(get_db)):
    """Рейтинг пользователей по рефералам"""
    # Топ-50 по количеству рефералов
    top_users = db.query(
        User.telegram_id,
        User.username,
        User.referral_count,
        User.referral_count_active
    ).order_by(User.referral_count.desc()).limit(50).all()

    return {
        "rating": [
            {
                "place": i + 1,
                "name": (u.username or f"User_{u.telegram_id}")[:4] + "***",
                "total": u.referral_count,
                "active": u.referral_count_active
            }
            for i, u in enumerate(top_users)
        ]
    }


@router.post("/claim/{milestone}")
async def claim_reward(
    milestone: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить награду за рефералов"""
    if milestone == 1 and user.referral_count >= 1:
        user.device_limit += 1
    elif milestone == 5 and user.referral_count >= 5:
        user.traffic_limit_gb += 0.5
    elif milestone == 15 and user.referral_count >= 15:
        user.traffic_limit_gb += 2.0
    elif milestone == 30 and user.referral_count >= 30:
        user.traffic_limit_gb += 5.0
    elif milestone == 50 and user.referral_count >= 50:
        user.traffic_limit_gb = 999999  # VIP
    elif milestone == 100 and user.referral_count >= 100:
        user.traffic_limit_gb = 999999  # Unlimited
    else:
        return {"error": "Milestone not reached"}

    db.commit()
    return {"status": "reward_claimed", "milestone": milestone}
