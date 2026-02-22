import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TIMEZONE = "Europe/Moscow"
BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '1296962464'))
BANK_CARD = os.getenv('BANK_CARD', '2200 1234 5678 9010')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@vladgrigoryan')

# ЮKassa настройки
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "your_shop_id")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "your_secret_key")
YOOKASSA_RETURN_URL = "https://t.me/pinkov300_bot"

# Пути к файлам
BASE_DIR = Path(__file__).parent
USERS_FILE = BASE_DIR / 'users_data.json'
TASKS_FILE = BASE_DIR / 'tasks_data.json'
PAYMENTS_FILE = BASE_DIR / 'payments_data.json'
INVITE_CODES_FILE = BASE_DIR / 'invite_codes.json'
WITHDRAWALS_FILE = BASE_DIR / 'withdrawals_data.json'
TRANSACTIONS_FILE = BASE_DIR / 'transactions_data.json'

# Тарифы подписки
TARIFFS = {
    "month": {
        "name": "Месячная подписка",
        "price": 300,
        "days": 30,
        "description": "Доступ на 30 дней"
    },
    "forever": {
        "name": "Пожизненная подписка",
        "price": 1990,
        "days": 36500,  # 100 лет (фактически навсегда)
        "description": "Доступ навсегда"
    }
}

# Настройки сертификатов
CERTIFICATES_DIR = "certificates/generated"
CERTIFICATES_BASE_URL = os.getenv("CERTIFICATES_BASE_URL", "https://ваш-домен.ру/certificates")

BOT_USERNAME = "pinkov300_bot"  

# ЧАСОВЫЕ ПОЯСА РОССИИ
RUSSIAN_TIMEZONES = {
    "Калининград (UTC+2)": "Europe/Kaliningrad",
    "Москва (UTC+3)": "Europe/Moscow", 
    "Самара (UTC+4)": "Europe/Samara",
    "Екатеринбург (UTC+5)": "Asia/Yekaterinburg",
    "Омск (UTC+6)": "Asia/Omsk",
    "Красноярск (UTC+7)": "Asia/Krasnoyarsk",
    "Иркутск (UTC+8)": "Asia/Irkutsk",
    "Якутск (UTC+9)": "Asia/Yakutsk",
    "Владивосток (UTC+10)": "Asia/Vladivostok",
    "Магадан (UTC+11)": "Asia/Magadan",
    "Камчатка (UTC+12)": "Asia/Kamchatka"
}

# Реферальная система
REFERRAL_LEVELS = {
    "legioner": {"min_refs": 1, "percent": 30, "name": "Легионер"},
    "centurion": {"min_refs": 30, "percent": 40, "name": "Центурион"}, 
    "imperator": {"min_refs": 300, "percent": 50, "name": "Император"}
}

# Настройки вывода средств
MIN_WITHDRAWAL = 300  # Минимальная сумма вывода
WITHDRAWAL_METHODS = {
    "bank_card": "💳 Банковская карта",
    "yoomoney": "ЮMoney",
    "sberbank": "Сбербанк Онлайн", 
    "tinkoff": "Тинькофф",
}

# Лимиты
DAILY_WITHDRAWAL_LIMIT = 50000  # Максимальный вывод в день
MAX_WITHDRAWALS_PER_DAY = 3     # Максимум заявок в день

# Система рангов
RANKS = {
    "putnik": {
        "completed_tasks": 0,
        "name": "🥋 Путник",
        "description": "Твой вызов: Довериться системе и честно выполнять задания.",
        "privileges": ["Бесплатный канал 300 ПИНКОВ"]
    },
    "voin": {
        "completed_tasks": 31,
        "name": "🛡 Воин", 
        "description": "Твой вызов: сделать дисциплину своей второй натурой.",
        "privileges": [
            "Набор эксклюзивных стикеров для мотивации",
        ]
    },
    "geroi": {
        "completed_tasks": 101,
        "name": "⚔️ Герой",
        "description": "Твой вызов: стать олицетворением силы воли для других.",
        "privileges": [
            "Возможность предлагать свои задания для системы",
        ]
    },
    "spartan": {
        "completed_tasks": 300,
        "name": "👑 Спартанец",
        "description": "Твой вызов: войти в историю.",
        "privileges": [
            "Бесплатный доступ в закрытую группу"
        ]
    }
}

# Ссылки для привилегий
PRIVILEGE_LINKS = {
    "putnik": {
        "Бесплатный канал 300 ПИНКОВ": "https://t.me/pinkov300"
    },
    "voin": {
        "Набор эксклюзивных стикеров для мотивации": "https://t.me/addstickers/pinkov30_stickers_by_TgEmodziBot",
    },
    "geroi": {
        "Возможность предлагать свои задания для системы": "https://t.me/pink300_suggestions",
    },
    "spartan": {
        "Бесплатный доступ в закрытую группу": "https://t.me/pink300_premium"
    }
}

# Типы инвайт-кодов
INVITE_CODE_TYPES = {
    # Обычные подписки
    "month": {"name": "Месячная подписка", "days": 30},
    "forever": {"name": "Пожизненная подписка", "days": 36500},
    
    # Подарочные подписки (покупка для друга)
    "gift_month": {"name": "🎁 Подарочная месячная подписка", "days": 30, "price": 300},
    "gift_forever": {"name": "🎁 Подарочная пожизненная подписка", "days": 36500, "price": 1990},
    
    # Сертификаты (админские, бесплатные)
    "certificate_month": {
        "name": "📅 Месячный сертификат",
        "days": 30,
        "price": 0
    },
    "certificate_forever": {
        "name": "♾️ Пожизненный сертификат", 
        "days": 36500,
        "price": 0
    },
}

# Время отправки заданий
TASK_TIME_HOUR = 9
TASK_TIME_MINUTE = 0
REMINDER_TIME_HOUR = 18
REMINDER_TIME_MINUTE = 30

# Лимиты для "Пинка другу"
PINK_FRIEND_LIMITS = {
    "free": {"links": 3, "daily_sends": 3},
    "premium": {"links": 10, "daily_sends": 30}
}

# Настройки массовой рассылки
MASS_NOTIFICATION_TYPES = {
    'all': 'Всем пользователям',
    'active': 'Активным пользователям',
    'inactive': 'Неактивным пользователям',
    'subscribed': 'С активной подпиской',
    'trial': 'В пробном периоде',
    'no_subscription': 'Без подписки'
}