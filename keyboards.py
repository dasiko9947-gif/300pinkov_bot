from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import config

# НОВОЕ ГЛАВНОЕ МЕНЮ
# НОВОЕ ГЛАВНОЕ МЕНЮ с кнопкой этапов
def get_main_menu(user_id=None):
    keyboard = [
        [KeyboardButton(text="Задание на сегодня ✅")],
        [KeyboardButton(text="Мой прогресс 🏆"), KeyboardButton(text="Подписка 💎")],
        [KeyboardButton(text="Мой легион ⚔️"), KeyboardButton(text="Сертификаты 🎁")],  # НОВАЯ КНОПКА
        [KeyboardButton(text="ЭТАПЫ 300 ПИНКОВ 📋")]
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

# Добавить в keyboards.py
def get_gift_subscription_keyboard():
    """Клавиатура для выбора подарка с ценами из config"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🎁 1 месяц - {config.TARIFFS['month']['price']} руб.",
                callback_data="gift_tariff_month"
            )],
            [InlineKeyboardButton(
                text=f"🎁 1 год - {config.TARIFFS['year']['price']} руб.",
                callback_data="gift_tariff_year"
            )],
            [InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="back_to_invite_codes"
            )]
        ]
    )

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
def get_payment_keyboard():
    """Клавиатура для оплаты подписки - с выбором этапа"""
    tariffs = config.TARIFFS
    
    keyboard = [
        [InlineKeyboardButton(
            text=f"📅 Месячная - {tariffs['month']['price']} руб.", 
            callback_data="tariff_with_stage_month"  # ИЗМЕНЕНО
        )],
        [InlineKeyboardButton(
            text=f"🎯 Годовая - {tariffs['year']['price']} руб.", 
            callback_data="tariff_with_stage_year"  # ИЗМЕНЕНО
        )],
        [InlineKeyboardButton(
            text=f"👥 Парная годовая - {tariffs['pair_year']['price']} руб.", 
            callback_data="tariff_with_stage_pair_year"  # ИЗМЕНЕНО
        )],
        [InlineKeyboardButton(
            text="🔙 Главное меню", 
            callback_data="back_to_main"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

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


# ========== КЛАВИАТУРЫ ДЛЯ ВЫБОРА ЭТАПОВ ==========

# ========== КЛАВИАТУРЫ ДЛЯ ВЫБОРА ЭТАПОВ ==========

def get_stages_keyboard(user_archetype: str, current_page: int = 0):
    """
    Клавиатура для выбора этапа (10 этапов, по 5 на странице)
    
    Args:
        user_archetype: 'spartan' или 'amazon'
        current_page: 0 или 1 (первая страница: этапы 1-5, вторая: этапы 6-10)
    """
    # Определяем названия этапов для каждого архетипа
    stage_titles = {
        'spartan': {
            1: "ПОЛЕ БИТВЫ",
            2: "ДОФАМИНОВАЯ БЛОКАДА",
            3: "НЕЙРОННАЯ ГВАРДИЯ",
            4: "СПАРТАНСКИЙ ДУХ",
            5: "ОДИНОЧНЫЙ ПИКЕТ",
            6: "ПАЛАТКА ПОМОЩИ",
            7: "ФИНАНСОВАЯ РЕФОРМА",
            8: "ЗОНА ДИСКОМФОРТА",
            9: "СОЦИАЛЬНЫЙ ПРОРЫВ",
            10: "РЕВОЛЮЦИЯ СОЗНАНИЯ"
        },
        'amazon': {
            1: "ПОЛЕ БИТВЫ",
            2: "ДОФАМИНОВАЯ БЛОКАДА",
            3: "НЕЙРОННАЯ ГВАРДИЯ",
            4: "ГРАЦИОЗНОЕ ТЕЛО",
            5: "ЖЕНСКАЯ ДИСЦИПЛИНА",
            6: "ПРОСТРАНСТВО ЗАБОТЫ",
            7: "ЖЕНСКАЯ ФИНАНСОВАЯ МУДРОСТЬ",
            8: "РАСШИРЕНИЕ ГРАНИЦ",
            9: "СОЦИАЛЬНЫЙ ПРОРЫВ",
            10: "ПРОБУЖДЕНИЕ ЖЕНСТВЕННОСТИ"
        }
    }
    
    buttons = []
    
    # Определяем диапазон этапов для текущей страницы
    if current_page == 0:
        stage_range = range(1, 6)  # Этапы 1-5
        next_page = 1
        prev_page = None
    else:
        stage_range = range(6, 11)  # Этапы 6-10
        next_page = None
        prev_page = 0
    
    # Создаем кнопки для этапов текущей страницы
    for stage_num in stage_range:
        # Получаем название этапа для соответствующего архетипа
        stage_title = stage_titles.get(user_archetype, stage_titles['spartan']).get(stage_num, f'ЭТАП {stage_num}')
        
        # Укорачиваем название для кнопки (первые 20 символов)
        short_title = stage_title[:20] + "..." if len(stage_title) > 20 else stage_title
        
        buttons.append([
            InlineKeyboardButton(
                text=f"📌 Этап {stage_num}: {short_title}",
                callback_data=f"view_stage_{stage_num}"
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    
    if prev_page is not None:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"stages_page_{prev_page}"
        ))
    
    if next_page is not None:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=f"stages_page_{next_page}"
        ))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Кнопка возврата к тарифам
    buttons.append([
        InlineKeyboardButton(
            text="🔙 Назад к выбору тарифа",
            callback_data="back_to_tariffs"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_stage_detail_keyboard(stage_num: int, tariff_id: str):
    """
    Клавиатура для детального просмотра этапа
    
    Args:
        stage_num: номер этапа (1-10)
        tariff_id: ID выбранного тарифа (month/year/pair_year)
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Выбрать этот этап",
                callback_data=f"select_stage_{stage_num}_{tariff_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ К списку этапов",
                callback_data=f"back_to_stages_{tariff_id}"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== КЛАВИАТУРЫ ДЛЯ ПРОСМОТРА ЭТАПОВ ИЗ ГЛАВНОГО МЕНЮ ==========

def get_stages_main_menu_keyboard(user_archetype: str = 'spartan', current_page: int = 0):
    """
    Клавиатура для просмотра этапов из главного меню
    
    Args:
        user_archetype: 'spartan' или 'amazon' (по умолчанию 'spartan')
        current_page: 0 или 1 (первая страница: этапы 1-5, вторая: этапы 6-10)
    """
    # Названия этапов для отображения
    stage_titles = {
        1: "ПОЛЕ БИТВЫ",
        2: "ДОФАМИНОВАЯ БЛОКАДА",
        3: "НЕЙРОННАЯ ГВАРДИЯ",
        4: "СПАРТАНСКИЙ ДУХ / ГРАЦИОЗНОЕ ТЕЛО",
        5: "ОДИНОЧНЫЙ ПИКЕТ / ЖЕНСКАЯ ДИСЦИПЛИНА",
        6: "ПАЛАТКА ПОМОЩИ / ПРОСТРАНСТВО ЗАБОТЫ",
        7: "ФИНАНСОВАЯ РЕФОРМА / ЖЕНСКАЯ ФИНАНСОВАЯ МУДРОСТЬ",
        8: "ЗОНА ДИСКОМФОРТА / РАСШИРЕНИЕ ГРАНИЦ",
        9: "СОЦИАЛЬНЫЙ ПРОРЫВ",
        10: "РЕВОЛЮЦИЯ СОЗНАНИЯ / ПРОБУЖДЕНИЕ ЖЕНСТВЕННОСТИ"
    }
    
    buttons = []
    
    # Определяем диапазон этапов для текущей страницы
    if current_page == 0:
        stage_range = range(1, 6)  # Этапы 1-5
        next_page = 1
        prev_page = None
    else:
        stage_range = range(6, 11)  # Этапы 6-10
        next_page = None
        prev_page = 0
    
    # Создаем кнопки для этапов текущей страницы
    for stage_num in stage_range:
        stage_title = stage_titles.get(stage_num, f'ЭТАП {stage_num}')
        
        # Укорачиваем название для кнопки
        short_title = stage_title[:20] + "..." if len(stage_title) > 20 else stage_title
        
        buttons.append([
            InlineKeyboardButton(
                text=f"📌 Этап {stage_num}: {short_title}",
                callback_data=f"main_view_stage_{stage_num}"
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    
    if prev_page is not None:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"main_stages_page_{prev_page}"
        ))
    
    if next_page is not None:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=f"main_stages_page_{next_page}"
        ))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Кнопка выбора архетипа (если не выбран)
    if user_archetype is None:
        buttons.append([
            InlineKeyboardButton(text="⚔️ Спартанец", callback_data="main_set_archetype_spartan"),
            InlineKeyboardButton(text="🛡️ Амазонка", callback_data="main_set_archetype_amazon")
        ])
    
    # Кнопка возврата в главное меню
    buttons.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_stage_main_detail_keyboard(stage_num: int):
    """
    Клавиатура для детального просмотра этапа из главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="💎 Оплатить подписку и начать",
                callback_data="go_to_subscription"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ К списку этапов",
                callback_data="back_to_main_stages"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# КЛАВИАТУРА ДЛЯ ПОДПИСКИ (С ВЫБОРОМ ЭТАПА)
def get_payment_keyboard_with_stages():
    """Клавиатура для оплаты подписки - С выбором этапа (для кнопки Подписка)"""
    tariffs = config.TARIFFS
    
    keyboard = [
        [InlineKeyboardButton(
            text=f"📅 Месячная - {tariffs['month']['price']} руб.", 
            callback_data="tariff_with_stage_month"
        )],
        [InlineKeyboardButton(
            text=f"🎯 Годовая - {tariffs['year']['price']} руб.", 
            callback_data="tariff_with_stage_year"
        )],
        [InlineKeyboardButton(
            text=f"👥 Парная годовая - {tariffs['pair_year']['price']} руб.", 
            callback_data="tariff_with_stage_pair_year"
        )],
        [InlineKeyboardButton(
            text="🔙 Главное меню", 
            callback_data="back_to_main"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# КЛАВИАТУРА ДЛЯ ЭТАПОВ (БЕЗ ВЫБОРА ЭТАПА)
def get_payment_keyboard_direct():
    """Клавиатура для оплаты подписки - БЕЗ выбора этапа (для кнопки Этапы)"""
    tariffs = config.TARIFFS
    
    keyboard = [
        [InlineKeyboardButton(
            text=f"📅 Месячная - {tariffs['month']['price']} руб.", 
            callback_data="tariff_direct_month"  # ДРУГОЙ callback
        )],
        [InlineKeyboardButton(
            text=f"🎯 Годовая - {tariffs['year']['price']} руб.", 
            callback_data="tariff_direct_year"  # ДРУГОЙ callback
        )],
        [InlineKeyboardButton(
            text=f"👥 Парная годовая - {tariffs['pair_year']['price']} руб.", 
            callback_data="tariff_direct_pair_year"  # ДРУГОЙ callback
        )],
        [InlineKeyboardButton(
            text="🔙 Назад к этапам", 
            callback_data="back_to_main_stages"  # ВОЗВРАТ К ЭТАПАМ
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

