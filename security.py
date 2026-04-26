import hmac
import hashlib
import json
from urllib.parse import parse_qsl

from app.core.config import settings


def validate_telegram_init_data(init_data: str) -> dict:
    """Валидация данных от Telegram Web App"""
    try:
        parsed_data = dict(parse_qsl(init_data))
        received_hash = parsed_data.pop('hash', None)

        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(parsed_data.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            settings.TELEGRAM_BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if calculated_hash != received_hash:
            return None

        user_data = json.loads(parsed_data.get('user', '{}'))
        return user_data

    except Exception:
        return None
