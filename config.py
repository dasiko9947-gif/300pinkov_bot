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

# Тарифы
TARIFFS = {
    "month": {"name": "Месячная подписка", "price": 3, "days": 30},  # 30 дней, а не 31
    "year": {"name": "Годовая подписка", "price": 3000, "days": 365},
    "pair_year": {"name": "👥 Парная годовая", "price": 5000, "days": 365},
}
# Настройки сертификатов
CERTIFICATES_DIR = "certificates/generated"
CERTIFICATES_BASE_URL = os.getenv("CERTIFICATES_BASE_URL", "https://ваш-домен.ру/certificates")



# Добавьте или обновите эти настройки:# В начало файла config.py, после импортов добавьте:
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Загрузка этапов из stages.json
BASE_DIR = Path(__file__).parent
STAGES_FILE = BASE_DIR / 'stages.json'

try:
    with open(STAGES_FILE, 'r', encoding='utf-8') as f:
        STAGES = json.load(f)
    logger.info(f"✅ Загружено {len(STAGES)} этапов из stages.json")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки stages.json: {e}")
    STAGES = {}
BOT_USERNAME = "pinkov300_bot"  
SUPPORT_USERNAME = "@vladgrigoryan" 
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

# Настройки вывода средств
MIN_WITHDRAWAL = 300  # Минимальная сумма вывода
WITHDRAWAL_METHODS = {
    "bank_card": "💳 Банковская карта",
    "yoomoney": "ЮMoney",
    "sberbank": "Сбербанк Онлайн", 
    "tinkoff": "Тинькофф",
}

# Файлы данных
WITHDRAWALS_FILE = BASE_DIR / 'withdrawals_data.json'
TRANSACTIONS_FILE = BASE_DIR / 'transactions_data.json'

# Лимиты
DAILY_WITHDRAWAL_LIMIT = 50000  # Максимальный вывод в день
MAX_WITHDRAWALS_PER_DAY = 3     # Максимум заявок в день

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
        "Набор эксклюзивных стикеров для мотивации": "https://t.me/addstickers/pinkov30_stickers_by_TgEmodziBot",
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
    # Существующие типы
    "month": {"name": "Месячная подписка", "days": 30},
    "year": {"name": "Годовая подписка", "days": 365},
    "pair_year": {"name": "Парная годовая", "days": 365},
    "gift_month": {"name": "🎁 Подарочная подписка на 1 месяц", "days": 30, "price": 300},
    "gift_year": {"name": "🎁 Подарочная подписка на 1 год", "days": 365, "price": 3000},
    "gift_subscription": {"name": "🎁 Подарочная подписка", "days": 30, "price": 0},
    
    # Новые типы для сертификатов
    "certificate_month": {
        "name": "📅 Месячный сертификат",
        "days": 30,
        "price": 0
    },
    "certificate_year": {
        "name": "📆 Годовой сертификат", 
        "days": 365,
        "price": 0
    },
    
    # Для создания через функцию
    "certificate": {
        "name": "Сертификат",
        "days": 30,
        "price": 0
    }
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