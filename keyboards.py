from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import config

# НОВОЕ ГЛАВНОЕ МЕНЮ
def get_main_menu(user_id=None):
    keyboard = [
        [KeyboardButton(text="Задание на сегодня ✅")],
        [KeyboardButton(text="Мой прогресс 🏆"), KeyboardButton(text="Подписка 💎")],
        [KeyboardButton(text="Сертификаты 🎁"), KeyboardButton(text="Мой легион ⚔️")]  # ИЗМЕНИЛИ ЗДЕСЬ
    ]
    
    if user_id == config.ADMIN_ID:
        keyboard.append([KeyboardButton(text="⚙️ Админ-панель")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Выбор архетипа
archetype_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⚔️ Спартанец"), KeyboardButton(text="🛡️ Амазонка")]
    ],
    resize_keyboard=True
)

# Обновленная клавиатура для заданий
task_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ ГОТОВО"), KeyboardButton(text="⏭️ ПРОПУСТИТЬ")],
        [KeyboardButton(text="📤 Пинок другу"), KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

def get_gift_subscription_keyboard():
    """Клавиатура для выбора тарифа подарочного сертификата"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📅 Месячная подписка - 300 руб.", 
                callback_data="gift_tariff_month"
            )],
            [InlineKeyboardButton(
                text="♾️ Пожизненная подписка - 1990 руб.", 
                callback_data="gift_tariff_forever"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад к сертификатам", 
                callback_data="back_to_certificates"
            )]
        ]
    )
    return keyboard
def get_gift_confirmation_keyboard(invite_code, payment_id=None):
    """Клавиатура после создания инвайт-кода для подарка"""
    buttons = []
    
    if payment_id:
        buttons.append([
            InlineKeyboardButton(
                text="💳 Оплатить подписку", 
                callback_data=f"process_gift_payment_{payment_id}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="📋 Скопировать код", 
            callback_data=f"copy_gift_code_{invite_code}"
        )
    ])
    
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_gift_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
# Админская клавиатура
def get_admin_keyboard():
    """Клавиатура для админ-панели с двумя столбцами"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            # Первая строка из двух столбцов
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="👥 Пользователи")
            ],
            # Вторая строка из двух столбцов
            [
                KeyboardButton(text="🎫 Инвайт-коды"),
                KeyboardButton(text="🎁 Создать сертификат")
            ],
            # Третья строка из двух столбцов
            [
                KeyboardButton(text="📤 Заявки на вывод"),
                KeyboardButton(text="📢 Массовая рассылка")
            ],
            # Отдельная кнопка внизу
            [
                KeyboardButton(text="🔙 Главное меню")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

admin_keyboard = get_admin_keyboard()

# РАЗДЕЛ ПОДПИСКИ (очищенный)
# В файле keyboards.py обновите функцию get_payment_keyboard:

def get_payment_keyboard():
    """Клавиатура для оплаты подписки"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📅 Месячная - 300 руб.", 
                callback_data="tariff_month"
            )],
            [InlineKeyboardButton(
                text="♾️ Пожизненная - 1990 руб.", 
                callback_data="tariff_forever"
            )],
            [InlineKeyboardButton(
                text="🎫 Есть инвайт-код", 
                callback_data="activate_invite"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад", 
                callback_data="back_to_main"
            )]
        ]
    )
    return keyboard
# НОВЫЙ РАЗДЕЛ ИНВАЙТ-КОДОВ
def get_invite_codes_keyboard():
    """Клавиатура для раздела Сертификаты 🎁"""
    keyboard = [
        [InlineKeyboardButton(
            text="🎁 Купить подарочный сертификат",  # ПЕРВАЯ КНОПКА
            callback_data="gift_subscription"
        )],
        [InlineKeyboardButton(
            text="🎫 Активировать инвайт-код",  # ВТОРАЯ КНОПКА
            callback_data="activate_invite"
        )],
        [InlineKeyboardButton(
            text="🔙 Главное меню", 
            callback_data="back_to_main"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# РАЗДЕЛ МОЙ ЛЕГИОН
# РАЗДЕЛ МОЙ ЛЕГИОН (упрощенная версия - может не понадобиться)
def get_my_legion_keyboard():
    """Клавиатура для раздела Мой легион"""
    keyboard = [
        [InlineKeyboardButton(
            text="💰 Мои начисления", 
            callback_data="my_earnings"
        )],
        [InlineKeyboardButton(
            text="🔙 Главное меню", 
            callback_data="back_to_main"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура прогресса
def get_my_rank_keyboard():
    """Клавиатура для раздела прогресса"""
    buttons = [
        [InlineKeyboardButton(text="📋 Полная система рангов", callback_data="full_ranks_system")],
        [InlineKeyboardButton(text="◀️ Назад в прогресс", callback_data="back_to_progress")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_my_referral_keyboard():
    """Клавиатура для реферальной системы БЕЗ кнопки вывода"""
    keyboard = [
        [InlineKeyboardButton(text="📤 Отправить приглашение", switch_inline_query="invite")],
        [InlineKeyboardButton(text="💰 Мои начисления", callback_data="my_earnings")],
        [InlineKeyboardButton(text="🤝 Как работает система", callback_data="full_referral_system")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Админские клавиатуры
def get_admin_invite_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать инвайт-код", callback_data="invite_create")],
            [InlineKeyboardButton(text="📋 Список активных кодов", callback_data="invite_list")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            
        ]
    )

def get_invite_code_types_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Пробный период (3 дня)", callback_data="invite_type_trial")],
            [InlineKeyboardButton(text="🚀 4-дневный спринт Детокс", callback_data="invite_type_detox_sprint")],
            [InlineKeyboardButton(text="📅 Месячная подписка", callback_data="invite_type_month")],
            [InlineKeyboardButton(text="🎯 Годовая подписка", callback_data="invite_type_year")],
            [InlineKeyboardButton(text="👥 Парная (год)", callback_data="invite_type_pair_year")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ]
    )

def get_admin_stats_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📈 Общая статистика", callback_data="admin_stats_general")],
            [InlineKeyboardButton(text="👥 Активные пользователи", callback_data="admin_stats_active")],
            [InlineKeyboardButton(text="💎 Подписки", callback_data="admin_stats_subscriptions")],
            [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")]
        ]
    )

def get_admin_users_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin_users_list")],
            [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_users_search")],
            [InlineKeyboardButton(text="✉️ Написать пользователю", callback_data="admin_users_message")],
            [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")]
        ]
    )

# Клавиатура для тестирования рангов
def get_test_ranks_keyboard():
    """Клавиатура для тестирования системы рангов"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Путник (0 заданий)", callback_data="test_rank_putnik")],
            [InlineKeyboardButton(text="🔵 Воин (30 заданий)", callback_data="test_rank_voin")],
            [InlineKeyboardButton(text="🟣 Герой (100 заданий)", callback_data="test_rank_geroi")],
            [InlineKeyboardButton(text="🟠 Спартанец (300 заданий)", callback_data="test_rank_spartan")],
            [InlineKeyboardButton(text="🔄 Сбросить тест", callback_data="test_rank_reset")],
            [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")]
        ]
    )

# Клавиатуры для отправки пинков
def get_current_pink_keyboard(task_day):
    keyboard = [
        [InlineKeyboardButton(text="📤 Отправить другу", switch_inline_query="")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main_from_task")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_send_to_friend_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="📤 Пригласить друга", switch_inline_query="")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатуры выбора часового пояса и готовности
def get_timezone_keyboard():
    keyboard = [
        [KeyboardButton(text="Калининград (UTC+2)")],
        [KeyboardButton(text="Москва (UTC+3)")],
        [KeyboardButton(text="Самара (UTC+4)")],
        [KeyboardButton(text="Екатеринбург (UTC+5)")],
        [KeyboardButton(text="Омск (UTC+6)")],
        [KeyboardButton(text="Красноярск (UTC+7)")],
        [KeyboardButton(text="Иркутск (UTC+8)")],
        [KeyboardButton(text="Якутск (UTC+9)")],
        [KeyboardButton(text="Владивосток (UTC+10)")],
        [KeyboardButton(text="Магадан (UTC+11)")],
        [KeyboardButton(text="Камчатка (UTC+12)")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_ready_keyboard():
    keyboard = [
        [KeyboardButton(text="✅ Да, я готов начать!")],
        [KeyboardButton(text="❌ Нет, я передумал")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# МЕНЮ МАССОВОЙ РАССЫЛКИ
def get_mass_notification_keyboard():
    """Клавиатура для массовой рассылки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Всем пользователям", callback_data="mass_all")],
            [InlineKeyboardButton(text="✅ Активным", callback_data="mass_active")],
            [InlineKeyboardButton(text="❌ Неактивным", callback_data="mass_inactive")],
            [InlineKeyboardButton(text="💎 С подпиской", callback_data="mass_subscribed")],
            [InlineKeyboardButton(text="🎁 В пробном периоде", callback_data="mass_trial")],
            [InlineKeyboardButton(text="🚫 Без подписки", callback_data="mass_no_sub")],
            [InlineKeyboardButton(text="📊 Просмотр прошлых рассылок", callback_data="mass_history")],
            [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")]
        ]
    )

