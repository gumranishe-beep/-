from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, BigInteger
from datetime import datetime

from app.core.config import settings

# Для SQLite используем синхронный движок (для простоты)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://").replace("sqlite://", "sqlite:///"),
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Модели
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    photo_url = Column(String(500))

    # Подписка
    is_active = Column(Boolean, default=True)
    traffic_used_gb = Column(Float, default=0.0)
    traffic_limit_gb = Column(Float, default=10.0)  # Бесплатно 10 ГБ
    device_limit = Column(Integer, default=3)

    # Рефералы
    referrer_id = Column(BigInteger, nullable=True)
    referral_count = Column(Integer, default=0)
    referral_count_active = Column(Integer, default=0)

    # Шиба
    shiba_last_fed = Column(DateTime, nullable=True)
    shiba_hunger = Column(Integer, default=100)
    shiba_mood = Column(String(20), default="happy")

    # VPN
    vpn_config = Column(Text, nullable=True)
    vpn_server = Column(String(10), nullable=True)
    vpn_connected_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True)
    name = Column(String(100))
    device_type = Column(String(20), default="phone")
    public_key = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReferralLog(Base):
    __tablename__ = "referral_logs"

    id = Column(Integer, primary_key=True)
    referrer_id = Column(BigInteger, index=True)
    referred_id = Column(BigInteger)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyQuest(Base):
    __tablename__ = "daily_quests"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True)
    quest_date = Column(DateTime)
    quest_type = Column(String(50))  # feed, connect, share
    completed = Column(Boolean, default=False)
    reward_mb = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True)
    name = Column(String(100))
    country = Column(String(50))
    endpoint = Column(String(100))
    port = Column(Integer, default=51820)
    is_active = Column(Boolean, default=True)
    load_percent = Column(Integer, default=0)


async def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
