import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
TIMEZONE = "Europe/Moscow"
BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '1296962464'))
BANK_CARD = os.getenv('BANK_CARD', '2200 1234 5678 9010')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@admin')
# ЮKassa настройки
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "your_shop_id")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "your_secret_key")
YOOKASSA_RETURN_URL = "https://t.me/pinkov300_bot"  # URL для возврата после оплаты
# Пути к файлам
BASE_DIR = Path(__file__).parent
USERS_FILE = BASE_DIR / 'users_data.json'
TASKS_FILE = BASE_DIR / 'tasks_data.json'
PAYMENTS_FILE = BASE_DIR / 'payments_data.json'
INVITE_CODES_FILE = BASE_DIR / 'invite_codes.json'
STAGES_FILE = BASE_DIR / "stages.json" 
# Тарифы
TARIFFS = {
    "month": {"name": "Месячная подписка", "price": 300, "days": 30},
    "year": {"name": "Годовая подписка", "price": 3000, "days": 365},
    "pair_year": {"name": "👥 Парная годовая", "price": 5000, "days": 365},  # Единственная парная подписка
    "trial_ruble": {"name": "Пробный период 3 дня", "price": 1, "days": 3, "auto_renewal_price": 300}
}


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
# Разделение тарифов для раннего доступа

# Реферальная система
REFERRAL_LEVELS = {
    "legioner": {"min_refs": 1, "percent": 30, "name": "Легионер"},
    "centurion": {"min_refs": 30, "percent": 40, "name": "Центурион"},
    "imperator": {"min_refs": 300, "percent": 50, "name": "Император"}
}

# Новая система рангов (основана на выполненных заданиях)
RANKS = {
    "putnik": {
        "completed_tasks": 0,  # 0-30 выполненных заданий
        "name": "🥋 Путник",
        "description": "Твой вызов: Довериться системе и честно выполнять задания.",
        "privileges": ["Бесплатный канал 300 ПИНКОВ"]
    },
    "voin": {
        "completed_tasks": 31,  # 31-100 выполненных заданий
        "name": "🛡 Воин", 
        "description": "Твой вызов: сделать дисциплину своей второй натурой.",
        "privileges": [
            "Набор эксклюзивных стикеров для мотивации",
        ]
    },
    "geroi": {
        "completed_tasks": 101,  # 101-299 выполненных заданий
        "name": "⚔️ Герой",
        "description": "Твой вызов: стать олицетворением силы воли для других.",
        "privileges": [
            "Возможность предлагать свои задания для системы",
        ]
    },
    "spartan": {
        "completed_tasks": 300,  # 300+ выполненных заданий
        "name": "👑 Спартанец",
        "description": "Твой вызов: войти в историю.",
        "privileges": [
            "Бесплатный доступ в закрытую группу"
        ]
    }
}

# Ссылки для привилегий (хранятся отдельно)
PRIVILEGE_LINKS = {
    "putnik": {
        "Бесплатный канал 300 ПИНКОВ": "https://t.me/pinkov300"
    },
    "voin": {
        "Набор эксклюзивных стикеров для мотивации": "https://t.me/addstickers/Pink300Stickers",
    },
    "geroi": {
        "Возможность предлагать свои задания для системы": "https://t.me/pink300_suggestions",
    },
    "spartan": {
        "Бесплатный доступ в закрытую группу": "https://t.me/pink300_premium"
    }
}

# Тип инвайт-кода для спринта
INVITE_CODE_TYPES = {
    "trial": {"name": "Пробный период", "days": 3},
    "month": {"name": "Месячная подписка", "days": 30},
    "year": {"name": "Годовая подписка", "days": 365},
    "pair_year": {"name": "Парная годовая", "days": 365},  # Обновить если нужно
    "detox_sprint": {"name": "4-дневный спринт Детокс", "days": 4}
}
# Время отправки заданий
TASK_TIME_HOUR = 15
TASK_TIME_MINUTE = 22
REMINDER_TIME_HOUR = 18
REMINDER_TIME_MINUTE = 30

MAX_POSTPONED_TASKS = 300
# Лимиты для "Пинка другу"
PINK_FRIEND_LIMITS = {
    "free": {"links": 3, "daily_sends": 3},
    "premium": {"links": 10, "daily_sends": 30}

}


