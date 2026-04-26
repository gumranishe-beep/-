from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ShibaVPN"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./shiba_vpn.db"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""

    # VPN
    VPN_WIREGUARD_ENDPOINT: str = ""
    VPN_WIREGUARD_PORT: int = 51820
    VPN_DNS: str = "1.1.1.1, 8.8.8.8"

    # Limits
    FREE_DEVICE_LIMIT: int = 3
    FREE_TRAFFIC_LIMIT_GB: float = 10.0
    DAILY_FEED_BONUS_MB: int = 100

    # Referral
    REFERRAL_REWARD_DEVICE: int = 1      # +1 устройство за 1 реферала
    REFERRAL_REWARD_TRAFFIC_5: float = 0.5   # +500 МБ за 5
    REFERRAL_REWARD_TRAFFIC_15: float = 2.0  # +2 ГБ за 15
    REFERRAL_REWARD_TRAFFIC_30: float = 5.0  # +5 ГБ за 30
    REFERRAL_REWARD_VIP_50: bool = True      # VIP за 50
    REFERRAL_REWARD_UNLIMITED_100: bool = True  # Безлимит за 100

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
