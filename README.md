# 🐕 ShibaVPN — Бесплатный VPN в Telegram

Telegram Web App (мини-приложение) с VPN-сервисом и маскотом Шиба-Ину.

## ✨ Функции

- **🛡️ Бесплатный VPN** — WireGuard/VLESS конфигурации
- **🐕 Шиба-Ину** — анимированный маскот с разными состояниями
- **🍖 Кормление Шибы** — ежедневный бонус +100 МБ трафика
- **🎉 Танец Шибы** — анимация при подключении VPN
- **👥 Реферальная программа** — награды за друзей
- **🏆 Рейтинг** — топ пользователей
- **📱 До 3 устройств** — бесплатно
- **🌍 5 серверов** — Россия, Германия, Нидерланды, США, Сингапур

## 🚀 Быстрый старт

### 1. Создай бота в Telegram

Напиши [@BotFather](https://t.me/BotFather):
```
/newbot
```
Получи токен и настрой Web App:
```
/mybots → Выбери бота → Bot Settings → Menu Button → Configure menu button
```
Укажи URL твоего сервера (например `https://yourdomain.com`).

### 2. Настрой окружение

```bash
cp .env.example .env
# Отредактируй .env, добавь TELEGRAM_BOT_TOKEN
```

### 3. Запуск

**Docker:**
```bash
docker-compose up -d
```

**Локально:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. Настрой Webhook

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook"   -d "url=https://yourdomain.com/api/webhook"
```

## 📁 Структура проекта

```
shiba_vpn_bot/
├── frontend/
│   ├── index.html          # Главная страница Web App
│   └── static/
│       ├── css/style.css   # Стили + анимации Шибы
│       └── js/app.js       # Логика + Telegram SDK
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI приложение
│   │   ├── core/
│   │   │   ├── config.py   # Настройки
│   │   │   ├── database.py # SQLAlchemy модели
│   │   │   └── security.py # Валидация Telegram
│   │   └── api/
│   │       ├── auth.py     # Авторизация
│   │       ├── users.py    # Профиль, устройства
│   │       ├── vpn.py      # VPN серверы, конфиги
│   │       ├── referrals.py # Реферальная система
│   │       ├── shiba.py    # Кормление Шибы, квесты
│   │       └── admin.py    # Админ-панель
│   └── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## 🐕 Анимации Шибы

| Состояние | Анимация |
|-----------|----------|
| Голодная | Грустные глаза, опущенные уши |
| Сытая | Счастливый взгляд, виляние хвостом |
| VPN подключён | **ТАНЕЦ!** — прыжки, вращение, звёзды |
| Ест | Жевательная анимация, сердечки |
| Обычное | Моргание, движение ушами, виляние хвостом |

## 🔧 API Endpoints

| Endpoint | Описание |
|----------|----------|
| `POST /api/auth/login` | Авторизация через Telegram |
| `GET /api/users/profile` | Профиль пользователя |
| `GET /api/vpn/servers` | Список серверов |
| `POST /api/vpn/connect/{code}` | Подключение к VPN |
| `POST /api/shiba/feed` | Накормить Шибу |
| `GET /api/referrals/info` | Реферальная программа |
| `GET /api/referrals/rating` | Рейтинг |

## ⚠️ Важно

**Это шаблон проекта.** Для полноценного VPN нужно:

1. **VPN-серверы** — настрой WireGuard/VLESS на реальных серверах
2. **Генерация ключей** — интеграция с `wg` командой
3. **Мониторинг трафика** — сбор статистики с серверов
4. **Telegram Stars** — для монетизации (опционально)

## 📄 Лицензия

MIT License — делай что хочешь, но не забывай про Шибу! 🐕
