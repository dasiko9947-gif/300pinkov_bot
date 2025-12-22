import json
import aiofiles
import random
import string
from datetime import datetime, timedelta
import config
import logging

logger = logging.getLogger(__name__)

# ========== БАЗОВЫЕ ФУНКЦИИ РАБОТЫ С ФАЙЛАМИ ==========
async def get_current_postponed_count(user_data):
    """Возвращает количество текущих отложенных заданий"""
    postponed_tasks = user_data.get('postponed_tasks', [])
    active_postponed = [task for task in postponed_tasks if not task.get('completed', False)]
    return len(active_postponed)
# В начале файла utils.py после импортов ДОБАВЬТЕ:
# В utils.py, после других функций работы с рефералами
async def add_referral(referrer_id, referred_id):
    """Добавляет реферала к рефереру (старая функция для совместимости)"""
    try:
        referrer_data = await get_user(referrer_id)
        if referrer_data:
            referrals = referrer_data.get('referrals', [])
            if referred_id not in referrals:
                referrals.append(referred_id)
                referrer_data['referrals'] = referrals
                await save_user(referrer_id, referrer_data)
                return True
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка добавления реферала: {e}")
        return False
async def get_referral_level(ref_count):
    """Определяет уровень реферальной системы"""
    try:
        # БЕЗОПАСНАЯ ПРОВЕРКА ref_count
        if ref_count is None:
            ref_count = 0
        
        # Сначала проверяем высшие уровни
        levels = list(config.REFERRAL_LEVELS.items())
        levels.sort(key=lambda x: x[1]['min_refs'], reverse=True)
        
        for level_id, level_info in levels:
            if ref_count >= level_info['min_refs']:
                return level_id, level_info
        
        # Если не нашли, возвращаем начальный уровень
        return "legioner", config.REFERRAL_LEVELS["legioner"]
        
    except Exception as e:
        logger.error(f"❌ Ошибка определения реферального уровня: {e}")
        return "legioner", config.REFERRAL_LEVELS["legioner"]
async def read_json(file_path):
    """Асинхронно читает JSON файл"""
    try:
        if not file_path.exists():
            return {}
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content) if content else {}
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return {}

async def write_json(file_path, data):
    """Асинхронно записывает данные в JSON файл"""
    try:
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"Error writing {file_path}: {e}")

# ========== ФУНКЦИИ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========

async def get_user(user_id):
    """Получает данные пользователя"""
    users = await read_json(config.USERS_FILE)
    return users.get(str(user_id))

async def save_user(user_id, user_data):
    """Сохраняет данные пользователя"""
    users = await read_json(config.USERS_FILE)
    users[str(user_id)] = user_data
    await write_json(config.USERS_FILE, users)

async def get_all_users():
    """Получает всех пользователей"""
    return await read_json(config.USERS_FILE)

async def update_user_activity(user_id):
    """Обновляет время последней активности"""
    user_data = await get_user(user_id)
    if user_data:
        user_data['last_activity'] = datetime.now().isoformat()
        await save_user(user_id, user_data)

# ========== ФУНКЦИИ РАБОТЫ С ЗАДАНИЯМИ ==========

async def get_all_tasks():
    """Получает все задания"""
    return await read_json(config.TASKS_FILE)

async def get_task_by_day(day_number, archetype="spartan"):
    """Ищет задание по дню и архетипу (формат: task_1_spartan)"""
    logger.info(f"🔍 get_task_by_day: день {day_number}, архетип {archetype}")
    
    tasks = await get_all_tasks()
    logger.info(f"📁 Загружено задач: {len(tasks) if tasks else 0}")
    
    if not tasks:
        logger.error("❌ Файл задач пуст или не существует")
        return None, None  # Возвращаем None для обоих значений
    
    # ФОРМАТ: "task_1_spartan"
    task_key = f"task_{day_number}_{archetype}"
    logger.info(f"🔑 Ищу задание по ключу: {task_key}")
    
    if task_key in tasks:
        task = tasks[task_key]
        logger.info(f"✅ Найдено задание: {task_key}")
        return task_key, task
    
    logger.warning(f"⚠️ Задание дня {day_number} для архетипа {archetype} не найдено")
    
    # Для отладки показываем первые 5 ключей
    if tasks:
        available_keys = list(tasks.keys())[:5]
        logger.info(f"📋 Первые 5 ключей в файле: {available_keys}")
    
    return None, None  # ВСЕГДА возвращаем кортеж, даже если None
async def get_todays_tasks(user_data):
    """Возвращает задание на сегодня - ВСЕГДА возвращает список"""
    if not user_data:
        logger.info("❌ user_data is None в get_todays_tasks")
        return []  # ВСЕГДА возвращаем список, даже пустой
    
    logger.info(f"🔍 get_todays_tasks: проверяю пользователя")
    logger.info(f"   Текущий день: {user_data.get('current_day', 0)}")
    logger.info(f"   Архетип: {user_data.get('archetype')}")
    
    tasks = []  # Начинаем с пустого списка
    
    # Проверяем, может ли пользователь получать задания
    try:
        has_access = (
            await is_subscription_active(user_data) or 
            await is_in_trial_period(user_data)
        )
        
        if not has_access:
            logger.info(f"   ❌ Нет доступа к заданиям")
            return tasks  # Возвращаем пустой список
    except Exception as e:
        logger.error(f"❌ Ошибка проверки доступа: {e}")
        return tasks  # Возвращаем пустой список при ошибке
    
    # Проверяем, выполнено ли уже сегодняшнее задание
    if user_data.get('task_completed_today'):
        logger.info(f"   ⏸️ Задание уже выполнено сегодня")
        return tasks  # Возвращаем пустой список
    
    # Основное задание
    try:
        current_day = user_data.get('current_day', 0)
        next_day = current_day + 1
        
        logger.info(f"   📅 Следующий день: {next_day}")
        
        task_id, task = await get_task_by_day(next_day, user_data.get('archetype', 'spartan'))
        
        if task:
            if not isinstance(task, dict):
                logger.error(f"❌ Полученное задание не является словарем: {type(task)}")
                return tasks
                
            task_data = {
                'type': 'main',
                'day': next_day,
                'task_id': task_id,
                'text': task.get('text', 'Текст задания не найден'),
                'data': task
            }
            tasks.append(task_data)
            logger.info(f"   ✅ Найдено задание дня {next_day}")
        else:
            logger.warning(f"   ❌ Задание дня {next_day} не найдено")
    except Exception as e:
        logger.error(f"❌ Ошибка получения задания: {e}")
    
    logger.info(f"   📊 Всего заданий: {len(tasks)}")
    return tasks  # ВСЕГДА возвращаем список (даже пустой)
async def can_receive_new_task(user_data):
    """Проверяет, может ли пользователь получить новое задание"""
    logger.info(f"🔍 can_receive_new_task: проверяю пользователя")
    
    # Если пользователь в спринте - всегда может получить задание
    if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
        logger.info(f"   ✅ В спринте - может получить задание")
        return True
    
    # ПРОВЕРЯЕМ БЕСПЛАТНЫЙ ПРОБНЫЙ ПЕРИОД (первые 3 дня)
    if await is_in_trial_period(user_data):
        created_at_str = user_data.get('created_at')
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                days_passed = (datetime.now() - created_at).days
                
                # В БЕСПЛАТНОМ пробном периоде (первые 3 дня) можно получить 3 задания
                # НЕ проверяем completed_tasks_in_trial - просто даем доступ на 3 дня
                if days_passed < 3:
                    logger.info(f"✅ В БЕСПЛАТНОМ пробном периоде, день {days_passed + 1}")
                    return True
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки пробного периода: {e}")
    
    # Если задание уже выполнено сегодня - проверяем дату
    if user_data.get('task_completed_today', False):
        last_task_sent = user_data.get('last_task_sent')
        
        if not last_task_sent:
            logger.warning(f"⚠️ Противоречие: task_completed_today=True, но last_task_sent=None")
            return True
        
        try:
            last_date = datetime.fromisoformat(last_task_sent).date()
            today = datetime.now().date()
            
            if last_date < today:
                logger.info(f"✅ Задание выполнено вчера, можно получить новое")
                return True
            else:
                logger.info(f"⏸️ Задание уже выполнено сегодня")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки даты: {e}")
            return True
    
    # Проверяем платную подписку
    has_subscription = await is_subscription_active(user_data)
    
    logger.info(f"   Подписка активна: {has_subscription}")
    
    if not has_subscription:
        # Если нет подписки и не в БЕСПЛАТНОМ пробном периоде
        logger.info(f"❌ Нет доступа к заданиям (нет подписки и пробный период закончился)")
        return False
    
    # Проверяем, не получал ли уже задание сегодня
    last_task_sent = user_data.get('last_task_sent')
    if last_task_sent:
        try:
            last_date = datetime.fromisoformat(last_task_sent).date()
            today = datetime.now().date()
            
            if last_date == today:
                logger.info(f"⏸️ Задание уже отправлено сегодня")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки даты отправки: {e}")
    
    logger.info(f"✅ Может получить задание")
    return True
# ========== ФУНКЦИИ ПОДПИСКИ ==========

async def is_subscription_active(user_data):
    """Проверяет активна ли подписка (исправленная версия)"""
    if not user_data:
        logger.debug(f"❌ Нет данных пользователя")
        return False
    
    subscription_end = user_data.get('subscription_end')
    if not subscription_end:
        logger.debug(f"❌ Нет даты окончания подписки")
        return False
    
    try:
        from datetime import datetime
        import pytz
        
        # Пробуем ISO формат
        try:
            sub_end = datetime.fromisoformat(subscription_end)
        except ValueError:
            # Если не ISO формат, используем простой парсинг
            # Убираем временную зону если есть
            date_str = subscription_end.split('+')[0].split('.')[0]  # Убираем временную зону и микросекунды
            sub_end = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        
        # Убеждаемся, что у даты есть часовой пояс
        if sub_end.tzinfo is None:
            moscow_tz = pytz.timezone('Europe/Moscow')
            sub_end = moscow_tz.localize(sub_end)
        
        now = datetime.now(pytz.UTC)
        # Конвертируем sub_end в UTC для сравнения
        sub_end_utc = sub_end.astimezone(pytz.UTC)
        
        is_active = now < sub_end_utc
        
        # ЛОГИРУЕМ для отладки
        logger.info(f"🔍 Проверка подписки:")
        logger.info(f"   📅 Дата окончания: {subscription_end}")
        logger.info(f"   📅 Parsed date: {sub_end}")
        logger.info(f"   📅 UTC date: {sub_end_utc}")
        logger.info(f"   ⏰ Текущее время (UTC): {now.isoformat()}")
        logger.info(f"   ✅ Активна: {is_active}")
        
        if is_active:
            days_left = (sub_end_utc - now).days
            logger.info(f"   ⏰ Осталось дней: {days_left}")
        
        return is_active
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки подписки: {e}")
        logger.error(f"📅 Проблемная дата: {subscription_end}")
        logger.error(f"📊 Все данные пользователя: {user_data}")
        return False

async def add_subscription_days(user_data, days):
    """Добавляет дни подписки (исправленная версия)"""
    if not isinstance(user_data, dict):
        logger.error(f"❌ Ошибка: user_data не является словарем")
        user_data = {}
    
    from datetime import datetime, timedelta
    import pytz
    
    # Устанавливаем часовой пояс Москвы
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    
    # Если уже есть дата окончания подписки
    if user_data.get('subscription_end'):
        try:
            current_end_str = user_data['subscription_end']
            
            # Пробуем ISO формат
            try:
                current_end = datetime.fromisoformat(current_end_str)
            except ValueError:
                # Если не ISO формат, используем простой парсинг
                date_str = current_end_str.split('+')[0].split('.')[0]
                current_end = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            
            # Если дата без часового пояса, добавляем московский
            if current_end.tzinfo is None:
                current_end = moscow_tz.localize(current_end)
            
            # Конвертируем в московское время для сравнения
            current_end_moscow = current_end.astimezone(moscow_tz)
            
            if current_end_moscow > now:
                # Добавляем дни к текущей дате окончания
                new_end = current_end_moscow + timedelta(days=days)
            else:
                # Подписка истекла, начинаем с сегодня
                new_end = now + timedelta(days=days)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки даты окончания подписки: {e}")
            logger.error(f"📅 Проблемная дата: {user_data.get('subscription_end')}")
            # В случае ошибки начинаем с сегодня
            new_end = now + timedelta(days=days)
    else:
        # Первая подписка
        new_end = now + timedelta(days=days)
    
    # Сохраняем в ISO формате
    user_data['subscription_end'] = new_end.isoformat()
    
    # ЛОГИРУЕМ для отладки
    logger.info(f"📅 Добавление подписки: {days} дней")
    logger.info(f"📅 Текущее время (Москва): {now.isoformat()}")
    logger.info(f"📅 Новая дата окончания: {new_end.isoformat()}")
    
    return user_data
async def is_in_trial_period(user_data):
    """Проверяет, находится ли пользователь в БЕСПЛАТНОМ пробном периоде (3 дня)"""
    if not user_data:
        return False
    
    # Если у пользователя уже есть платная подписка - не в пробном
    if user_data.get('subscription_end'):
        try:
            sub_end = datetime.fromisoformat(user_data['subscription_end'])
            if datetime.now() < sub_end:
                return False  # Уже есть активная платная подписка
        except:
            pass
    
    created_at_str = user_data.get('created_at')
    if not created_at_str:
        return False
    
    try:
        created_at = datetime.fromisoformat(created_at_str)
        days_passed = (datetime.now() - created_at).days
        
        # БЕСПЛАТНЫЙ пробный период - 3 дня после регистрации
        # НЕ требуется оплата 1 рубля!
        return days_passed < 3
    except Exception:
        return False
async def get_trial_days_left(user_data):
    """Возвращает количество оставшихся дней пробного периода"""
    if not user_data or not user_data.get('created_at'):
        return 0
    
    try:
        created_at = datetime.fromisoformat(user_data['created_at'])
        days_passed = (datetime.now() - created_at).days
        days_left = 3 - days_passed
        return max(0, days_left)
    except:
        return 0

# ========== СИСТЕМА РАНГОВ ==========

async def update_user_rank(user_data):
    """Обновляет ранг пользователя на основе ВЫПОЛНЕННЫХ заданий"""
    completed_tasks = user_data.get('completed_tasks', 0)
    current_rank = user_data.get('rank', 'putnik')
    
    # Определяем новый ранг на основе выполненных заданий
    new_rank = "putnik"
    if completed_tasks >= 300:
        new_rank = "spartan"
    elif completed_tasks >= 101:
        new_rank = "geroi"
    elif completed_tasks >= 31:
        new_rank = "voin"
    
    # Если ранг изменился
    if current_rank != new_rank:
        user_data['rank'] = new_rank
        return True
    
    return False

async def get_rank_info(rank_id):
    """Возвращает информацию о ранге"""
    return config.RANKS.get(rank_id, {}).copy()

async def get_next_rank_info(current_rank):
    """Возвращает информацию о следующем ранге"""
    ranks_order = ["putnik", "voin", "geroi", "spartan"]
    if current_rank not in ranks_order:
        return config.RANKS.get("putnik", {})
    
    current_index = ranks_order.index(current_rank)
    if current_index < len(ranks_order) - 1:
        next_rank_id = ranks_order[current_index + 1]
        return config.RANKS.get(next_rank_id, {})
    return None

async def get_tasks_until_next_rank(current_rank, completed_tasks):
    """Возвращает количество заданий до следующего ранга"""
    next_rank = await get_next_rank_info(current_rank)
    if not next_rank:
        return 0
    
    tasks_needed = next_rank.get('completed_tasks', 0)
    tasks_left = tasks_needed - completed_tasks
    return max(0, tasks_left)

async def get_full_ranks_system_info(user_data):
    """Возвращает информацию о всех рангах с учетом прогресса пользователя"""
    completed_tasks = user_data.get('completed_tasks', 0)
    current_rank_id = user_data.get('rank', 'putnik')
    
    ranks_info = []
    
    for rank_id, rank_info in config.RANKS.items():
        rank_data = rank_info.copy()
        min_tasks = rank_info['completed_tasks']
        
        # Определяем статус ранга для пользователя
        if rank_id == current_rank_id:
            rank_data['status'] = 'current'
        elif min_tasks <= completed_tasks:
            rank_data['status'] = 'completed'
        else:
            rank_data['status'] = 'locked'
        
        # Получаем привилегии для отображения
        display_info = await get_rank_display_info(rank_id, user_data)
        rank_data['display_privileges'] = display_info['display_privileges']
        rank_data['has_access'] = display_info['has_access']
        
        ranks_info.append((rank_id, rank_data))
    
    return ranks_info

# ========== ПРИВИЛЕГИИ РАНГОВ ==========

async def get_privilege_links(rank_id, privilege_text):
    """Возвращает ссылку для конкретной привилегии"""
    links = config.PRIVILEGE_LINKS.get(rank_id, {})
    return links.get(privilege_text, None)

async def get_privileges_with_links(rank_id, user_data=None):
    """Возвращает привилегии с ссылками для текущего ранга"""
    rank_info = config.RANKS.get(rank_id, {})
    privileges = rank_info.get('privileges', [])
    
    result = []
    for privilege in privileges:
        link = await get_privilege_links(rank_id, privilege)
        result.append((privilege, link))
    
    return result

async def get_rank_display_info(rank_id, user_data=None):
    """Возвращает информацию о ранге для отображения с учетом доступа пользователя"""
    rank_info = config.RANKS.get(rank_id, {}).copy()
    
    if user_data:
        completed_tasks = user_data.get('completed_tasks', 0)
        target_rank_min_tasks = rank_info.get('completed_tasks', 0)
        has_access = completed_tasks >= target_rank_min_tasks
        
        privileges_with_links = await get_privileges_with_links(rank_id, user_data)
        
        # Форматируем привилегии для отображения
        display_privileges = []
        for privilege, link in privileges_with_links:
            if has_access and link:
                display_privileges.append(f"• {privilege}")
            elif has_access:
                display_privileges.append(f"• {privilege}")
            else:
                display_privileges.append(f"• 🔒 {privilege} (откроется после достижения)")
        
        rank_info['display_privileges'] = display_privileges
        rank_info['has_access'] = has_access
    else:
        rank_info['display_privileges'] = [f"• {p}" for p in rank_info.get('privileges', [])]
        rank_info['has_access'] = False
    
    return rank_info

# ========== РЕФЕРАЛЬНАЯ СИСТЕМА ==========

async def save_referral_relationship(referred_id, referrer_id):
    """Сохраняет связь реферал-реферер"""
    try:
        # Получаем данные реферала
        referred_data = await get_user(referred_id)
        if not referred_data:
            logger.error(f"❌ Реферал {referred_id} не найден")
            return False
        
        # Сохраняем кто пригласил
        referred_data['invited_by'] = referrer_id
        await save_user(referred_id, referred_data)
        
        # Добавляем в список рефералов реферера
        referrer_data = await get_user(referrer_id)
        if referrer_data:
            referrals = referrer_data.get('referrals', [])
            if referred_id not in referrals:
                referrals.append(referred_id)
                referrer_data['referrals'] = referrals
                await save_user(referrer_id, referrer_data)
                
                # Логируем действие
                await log_transaction(
                    user_id=referrer_id,
                    transaction_type="referral_add",
                    amount=0,
                    description=f"Добавлен реферал {referred_id}"
                )
                
                logger.info(f"✅ Реферал {referred_id} добавлен к {referrer_id}")
                return True
                
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения реферальной связи: {e}")
    
    return False

async def process_referral_payment(referred_id, amount, tariff_id):
    """Обрабатывает реферальное начисление при оплате"""
    try:
        # Получаем данные реферала
        referred_data = await get_user(referred_id)
        if not referred_data:
            logger.warning(f"ℹ️ Реферал {referred_id} не найден")
            return False, None, 0, 0
        
        # Получаем ID реферера
        referrer_id = referred_data.get('invited_by')
        if not referrer_id:
            logger.info(f"ℹ️ У пользователя {referred_id} нет реферера")
            return False, None, 0, 0
        
        # Получаем данные реферера
        referrer_data = await get_user(referrer_id)
        if not referrer_data:
            logger.warning(f"ℹ️ Реферер {referrer_id} не найден")
            return False, None, 0, 0
        
        # Рассчитываем уровень и процент
        referrals_count = len(referrer_data.get('referrals', []))
        level_id, level = await get_referral_level(referrals_count)  # ИСПОЛЬЗУЕМ async
        
        if not level:
            logger.error(f"❌ Не удалось определить реферальный уровень для {referrer_id}")
            return False, None, 0, 0
            
        percent = level.get('percent', 0)
        
        # Рассчитываем бонус
        bonus_amount = (amount * percent) / 100
        
        # Обновляем баланс реферера
        current_balance = referrer_data.get('referral_earnings', 0)
        referrer_data['referral_earnings'] = current_balance + bonus_amount
        
        # Сохраняем статистику
        if 'referral_stats' not in referrer_data:
            referrer_data['referral_stats'] = {}
        
        stats = referrer_data['referral_stats']
        stats['total_earned'] = stats.get('total_earned', 0) + bonus_amount
        stats['payments_count'] = stats.get('payments_count', 0) + 1
        stats['last_payment'] = datetime.now().isoformat()
        
        await save_user(referrer_id, referrer_data)
        
        # Логируем транзакцию
        await log_transaction(
            user_id=referrer_id,
            transaction_type="referral_bonus",
            amount=bonus_amount,
            description=f"Бонус за оплату {referred_id}. Тариф: {tariff_id}"
        )
        
        # Сохраняем детали платежа реферала
        await save_referral_payment_details(
            referrer_id=referrer_id,
            referred_id=referred_id,
            amount=amount,
            bonus=bonus_amount,
            percent=percent,
            tariff_id=tariff_id
        )
        
        logger.info(f"💰 Начислен бонус {bonus_amount} руб. рефереру {referrer_id}")
        return True, referrer_id, bonus_amount, percent
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки реферального платежа: {e}")
        return False, None, 0, 0

async def save_referral_payment_details(referrer_id, referred_id, amount, bonus, percent, tariff_id):
    """Сохраняет детали реферального платежа"""
    try:
        # Создаем запись о платеже
        payment_id = f"ref_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        
        payment_data = {
            'id': payment_id,
            'referrer_id': referrer_id,
            'referred_id': referred_id,
            'amount': amount,
            'bonus': bonus,
            'percent': percent,
            'tariff_id': tariff_id,
            'date': datetime.now().isoformat(),
            'status': 'completed'
        }
        
        # Сохраняем в файл реферальных платежей
        ref_payments = await read_json('referral_payments.json')
        if not ref_payments:
            ref_payments = {}
        
        ref_payments[payment_id] = payment_data
        await write_json('referral_payments.json', ref_payments)
        
        # Также сохраняем в транзакции реферера
        await log_transaction(
            user_id=referrer_id,
            transaction_type="referral_income",
            amount=bonus,
            description=f"Реферальный доход от {referred_id}"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения деталей платежа: {e}")

async def get_referral_statistics(user_id):
    """Получает детальную статистику по рефералам"""
    try:
        user_data = await get_user(user_id)
        if not user_data:
            return None
        
        referrals = user_data.get('referrals', [])
        total_earned = user_data.get('referral_earnings', 0)
        stats = user_data.get('referral_stats', {})
        
        # Собираем детали по каждому рефералу
        detailed_referrals = []
        active_count = 0
        total_payments = 0
        
        for ref_id in referrals:
            ref_data = await get_user(ref_id)
            if ref_data:
                # Проверяем активность
                is_active = await is_subscription_active(ref_data) or await is_in_trial_period(ref_data)
                if is_active:
                    active_count += 1
                
                # Считаем платежи этого реферала
                ref_payments = await get_referral_payments_by_referred(ref_id)
                ref_total = sum(p['amount'] for p in ref_payments)
                total_payments += ref_total
                
                detailed_referrals.append({
                    'id': ref_id,
                    'name': ref_data.get('first_name', 'Пользователь'),
                    'username': ref_data.get('username', ''),
                    'is_active': is_active,
                    'total_paid': ref_total,
                    'joined_date': ref_data.get('created_at', ''),
                    'payments_count': len(ref_payments)
                })
        
        # Получаем уровень
        level_id, level = await get_referral_level(len(referrals))
        
        return {
            'total_referrals': len(referrals),
            'active_referrals': active_count,
            'total_earned': total_earned,
            'level': level,
            'detailed_referrals': detailed_referrals,
            'stats': {
                'total_payments_from_referrals': total_payments,
                'conversion_rate': (active_count / len(referrals) * 100) if referrals else 0,
                'avg_payment_per_referral': total_payments / len(referrals) if referrals else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return None

# ========== СИСТЕМА ВЫВОДА СРЕДСТВ ==========

async def create_withdrawal_request(user_id, amount, method, details):
    """Создает заявку на вывод средств БЕЗ КОМИССИИ"""
    try:
        # Проверяем баланс
        user_data = await get_user(user_id)
        if not user_data:
            return False, "Пользователь не найден"
        
        balance = user_data.get('referral_earnings', 0)
        
        # Проверяем минимальную сумму (300 руб)
        if amount < config.MIN_WITHDRAWAL:
            return False, f"Минимальная сумма вывода: {config.MIN_WITHDRAWAL} руб."
        
        # Проверяем достаточно ли средств
        if amount > balance:
            return False, "Недостаточно средств на балансе"
        
        # Проверяем лимиты
        limit_check = await check_withdrawal_limits(user_id, amount)
        if not limit_check[0]:
            return False, limit_check[1]
        
        # БЕЗ КОМИССИИ - вся сумма идет пользователю
        amount_to_user = amount  # Полная сумма
        
        # Создаем ID заявки
        withdrawal_id = f"WD{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        
        # Данные заявки БЕЗ КОМИССИИ
        withdrawal_data = {
            'id': withdrawal_id,
            'user_id': user_id,
            'user_name': user_data.get('first_name', ''),
            'user_username': user_data.get('username', ''),
            'amount': amount,
            'amount_after_fee': amount_to_user,  # Та же сумма
            'fee': 0,  # Комиссия 0
            'fee_percent': 0,  # Процент 0
            'method': method,
            'details': details,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Резервируем средства
        user_data['referral_earnings'] = balance - amount
        user_data['reserved_for_withdrawal'] = user_data.get('reserved_for_withdrawal', 0) + amount
        await save_user(user_id, user_data)
        
        # Сохраняем заявку
        withdrawals = await read_json(config.WITHDRAWALS_FILE)
        if not withdrawals:
            withdrawals = {}
        
        withdrawals[withdrawal_id] = withdrawal_data
        await write_json(config.WITHDRAWALS_FILE, withdrawals)
        
        # Логируем транзакцию
        await log_transaction(
            user_id=user_id,
            transaction_type="withdrawal_request",
            amount=-amount,
            description=f"Заявка на вывод #{withdrawal_id}"
        )
        
        logger.info(f"✅ Создана заявка на вывод #{withdrawal_id}: {amount} руб. (без комиссии)")
        return True, withdrawal_id
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания заявки: {e}")
        return False, "Ошибка при создании заявки"
async def check_withdrawal_limits(user_id, amount):
    """Проверяет лимиты на вывод"""
    try:
        # Проверяем дневной лимит
        today = datetime.now().strftime('%Y-%m-%d')
        withdrawals = await read_json(config.WITHDRAWALS_FILE)
        
        if not withdrawals:
            return True, ""
        
        # Считаем сегодняшние выводы
        today_withdrawals = [
            w for w in withdrawals.values() 
            if w['user_id'] == user_id 
            and w['created_at'].startswith(today)
            and w['status'] in ['pending', 'processing', 'completed']
        ]
        
        today_total = sum(w['amount'] for w in today_withdrawals)
        
        if today_total + amount > config.DAILY_WITHDRAWAL_LIMIT:
            return False, f"Превышен дневной лимит. Осталось: {config.DAILY_WITHDRAWAL_LIMIT - today_total} руб."
        
        if len(today_withdrawals) >= config.MAX_WITHDRAWALS_PER_DAY:
            return False, f"Превышено количество заявок в день"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки лимитов: {e}")
        return False, "Ошибка проверки лимитов"

async def process_withdrawal(withdrawal_id, admin_id, action, comment=""):
    """Обрабатывает заявку на вывод"""
    try:
        withdrawals = await read_json(config.WITHDRAWALS_FILE)
        if withdrawal_id not in withdrawals:
            return False, "Заявка не найдена"
        
        withdrawal = withdrawals[withdrawal_id]
        user_id = withdrawal['user_id']
        
        if withdrawal['status'] != 'pending':
            return False, "Заявка уже обработана"
        
        user_data = await get_user(user_id)
        if not user_data:
            return False, "Пользователь не найден"
        
        if action == 'approve':
            # Вычитаем зарезервированные средства
            reserved = user_data.get('reserved_for_withdrawal', 0)
            user_data['reserved_for_withdrawal'] = max(0, reserved - withdrawal['amount'])
            
            withdrawal['status'] = 'processing'
            withdrawal['processed_by'] = admin_id
            withdrawal['processed_at'] = datetime.now().isoformat()
            withdrawal['comment'] = comment
            
            # Логируем
            await log_transaction(
                user_id=user_id,
                transaction_type="withdrawal_approved",
                amount=0,
                description=f"Вывод #{withdrawal_id} одобрен"
            )
            
            message = "✅ Заявка одобрена"
            
        elif action == 'complete':
            withdrawal['status'] = 'completed'
            withdrawal['completed_at'] = datetime.now().isoformat()
            
            # Логируем завершение
            await log_transaction(
                user_id=user_id,
                transaction_type="withdrawal_completed",
                amount=-withdrawal['amount'],
                description=f"Вывод #{withdrawal_id} завершен"
            )
            
            message = "✅ Вывод завершен"
            
        elif action == 'reject':
            # Возвращаем средства
            user_data['referral_earnings'] = user_data.get('referral_earnings', 0) + withdrawal['amount']
            reserved = user_data.get('reserved_for_withdrawal', 0)
            user_data['reserved_for_withdrawal'] = max(0, reserved - withdrawal['amount'])
            
            withdrawal['status'] = 'rejected'
            withdrawal['rejected_by'] = admin_id
            withdrawal['rejected_at'] = datetime.now().isoformat()
            withdrawal['reject_reason'] = comment
            
            # Логируем
            await log_transaction(
                user_id=user_id,
                transaction_type="withdrawal_rejected",
                amount=withdrawal['amount'],
                description=f"Вывод #{withdrawal_id} отклонен: {comment}"
            )
            
            message = "❌ Заявка отклонена"
        
        else:
            return False, "Неизвестное действие"
        
        # Сохраняем изменения
        await save_user(user_id, user_data)
        withdrawals[withdrawal_id] = withdrawal
        await write_json(config.WITHDRAWALS_FILE, withdrawals)
        
        logger.info(f"📋 Заявка #{withdrawal_id} обработана: {action}")
        return True, message
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки заявки: {e}")
        return False, "Ошибка обработки"

async def get_user_withdrawals(user_id, limit=10):
    """Получает историю выводов пользователя"""
    try:
        withdrawals = await read_json(config.WITHDRAWALS_FILE)
        if not withdrawals:
            return []
        
        user_withdrawals = [
            w for w in withdrawals.values() 
            if w['user_id'] == user_id
        ]
        
        # Сортируем по дате
        user_withdrawals.sort(key=lambda x: x['created_at'], reverse=True)
        
        return user_withdrawals[:limit]
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения истории выводов: {e}")
        return []

async def get_pending_withdrawals():
    """Получает все pending заявки"""
    try:
        withdrawals = await read_json(config.WITHDRAWALS_FILE)
        if not withdrawals:
            return []
        
        pending = [
            w for w in withdrawals.values() 
            if w['status'] == 'pending'
        ]
        
        pending.sort(key=lambda x: x['created_at'])
        return pending
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения pending заявок: {e}")
        return []

# ========== СИСТЕМА ТРАНЗАКЦИЙ ==========

async def log_transaction(user_id, transaction_type, amount, description=""):
    """Логирует финансовую транзакцию"""
    try:
        transaction_id = f"TX{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        
        transaction_data = {
            'id': transaction_id,
            'user_id': user_id,
            'type': transaction_type,  # referral_bonus, withdrawal_request, payment, etc.
            'amount': amount,
            'description': description,
            'timestamp': datetime.now().isoformat(),
            'balance_after': None  # Можно добавить расчет
        }
        
        # Получаем текущий баланс
        user_data = await get_user(user_id)
        if user_data:
            transaction_data['balance_after'] = user_data.get('referral_earnings', 0)
        
        # Сохраняем транзакцию
        transactions = await read_json(config.TRANSACTIONS_FILE)
        if not transactions:
            transactions = {}
        
        transactions[transaction_id] = transaction_data
        await write_json(config.TRANSACTIONS_FILE, transactions)
        
        logger.info(f"📊 Записана транзакция {transaction_id}: {transaction_type} {amount} руб.")
        
    except Exception as e:
        logger.error(f"❌ Ошибка логирования транзакции: {e}")

async def get_user_transactions(user_id, limit=20):
    """Получает историю транзакций пользователя"""
    try:
        transactions = await read_json(config.TRANSACTIONS_FILE)
        if not transactions:
            return []
        
        user_transactions = [
            t for t in transactions.values() 
            if t['user_id'] == user_id
        ]
        
        # Сортируем по дате
        user_transactions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return user_transactions[:limit]
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения транзакций: {e}")
        return []

# ========== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ==========

async def get_available_balance(user_id):
    """Получает доступный для вывода баланс"""
    try:
        user_data = await get_user(user_id)
        if not user_data:
            return 0
        
        total = user_data.get('referral_earnings', 0)
        reserved = user_data.get('reserved_for_withdrawal', 0)
        
        return max(0, total - reserved)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения доступного баланса: {e}")
        return 0

async def get_referral_payments_by_referred(referred_id):
    """Получает платежи конкретного реферала"""
    try:
        ref_payments = await read_json('referral_payments.json')
        if not ref_payments:
            return []
        
        payments = [
            p for p in ref_payments.values() 
            if p['referred_id'] == referred_id
        ]
        
        return payments
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения платежей реферала: {e}")
        return []

async def get_total_withdrawn(user_id):
    """Получает общую сумму выведенных средств"""
    try:
        withdrawals = await read_json(config.WITHDRAWALS_FILE)
        if not withdrawals:
            return 0
        
        user_withdrawals = [
            w for w in withdrawals.values() 
            if w['user_id'] == user_id and w['status'] == 'completed'
        ]
        
        return sum(w['amount'] for w in user_withdrawals)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения суммы выводов: {e}")
        return 0

# ========== ИНВАЙТ-КОДЫ ==========

async def generate_invite_code(length=8):
    """Генерирует случайный код"""
    return ''.join(random.choice(string.digits) for _ in range(length))

async def create_invite_code(code_type="month", days=None, max_uses=1, created_by=None, pair_owner=None):
    """Создает инвайт-код"""
    invite_codes = await read_json(config.INVITE_CODES_FILE)
    
    while True:
        code = await generate_invite_code()
        if code not in invite_codes:
            break
    
    if days is None:
        days = config.INVITE_CODE_TYPES.get(code_type, {}).get('days', 30)
    
    invite_data = {
        'code': code,
        'type': code_type,
        'days': days,
        'max_uses': max_uses,
        'used_count': 0,
        'created_by': created_by,
        'created_at': datetime.now().isoformat(),
        'used_by': [],
        'is_active': True,
        'name': config.INVITE_CODE_TYPES.get(code_type, {}).get('name', 'Подписка'),
        'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
    }
    
    # ТОЛЬКО для парных подписок
    if pair_owner is not None:
        invite_data['pair_owner'] = pair_owner
        invite_data['pair_owner_activated'] = True
    
    invite_codes[code] = invite_data
    await write_json(config.INVITE_CODES_FILE, invite_codes)
    return code

async def use_invite_code(code, user_id):
    """Активация инвайт-кода"""
    invite_codes = await read_json(config.INVITE_CODES_FILE)
    
    # Нормализуем код
    code = str(code).strip().upper()
    
    if code not in invite_codes:
        return False, "❌ Код не найден"
    
    invite = invite_codes[code]
    
    # Проверяем активность кода
    if not invite.get('is_active', True):
        return False, "❌ Код неактивен"
    
    # Проверяем срок действия
    try:
        expires_at = datetime.fromisoformat(invite.get('expires_at', ''))
        if datetime.now() > expires_at:
            invite['is_active'] = False
            await write_json(config.INVITE_CODES_FILE, invite_codes)
            return False, "❌ Срок действия кода истек"
    except:
        pass
    
    # Проверяем использование
    used_by = invite.get('used_by', [])
    
    # Проверяем, использовал ли пользователь уже этот код
    if str(user_id) in [str(uid) for uid in used_by]:
        return False, "❌ Вы уже использовали этот код"
    
    # Проверяем лимит использований
    if invite['used_count'] >= invite['max_uses']:
        invite['is_active'] = False
        await write_json(config.INVITE_CODES_FILE, invite_codes)
        return False, "❌ Код уже использован"
    
    # Активируем код
    invite['used_count'] += 1
    if 'used_by' not in invite:
        invite['used_by'] = []
    invite['used_by'].append(user_id)
    invite['last_used'] = datetime.now().isoformat()
    
    # Для одноразовых кодов деактивируем сразу
    if invite['max_uses'] == 1:
        invite['is_active'] = False
    
    await write_json(config.INVITE_CODES_FILE, invite_codes)
    
    return True, invite

async def get_all_invite_codes(include_hidden=False):
    """Возвращает все инвайт-коды"""
    invite_codes = await read_json(config.INVITE_CODES_FILE)
    
    if not include_hidden:
        # Фильтруем скрытые коды
        return {code: data for code, data in invite_codes.items() 
                if not data.get('is_hidden', False)}
    
    return invite_codes

# ========== ГЕНДЕРНЫЕ ОКОНЧАНИЯ ДЛЯ АРХЕТИПОВ ==========

async def get_gender_ending(user_data):
    """Возвращает правильные окончания в зависимости от архетипа"""
    archetype = user_data.get('archetype', 'spartan')
    
    if archetype == 'amazon':
        return {
            'subject': 'ты',           # вместо "ты" (нейтрально, но можно заменить)
            'verb_action': 'сделала',  # сделал/сделала
            'verb_started': 'начала',  # начал/начала
            'adjective': 'готова',     # готов/готова
            'person': 'Амазонка',      # обращение
            'pronoun': 'твоя',         # твой/твоя
            'ending_a': 'а',           # окончание для женского рода
            'ending_la': 'ла',         # прошедшее время жен.род
        }
    else:  # spartan по умолчанию
        return {
            'subject': 'ты',
            'verb_action': 'сделал',
            'verb_started': 'начал',
            'adjective': 'готов',
            'person': 'Спартанец',
            'pronoun': 'твой',
            'ending_a': '',
            'ending_la': 'л',
        }

async def format_gender_text(text, user_data):
    """Форматирует текст с учетом гендерных окончаний"""
    endings = await get_gender_ending(user_data)
    
    # Заменяем плейсхолдеры
    replacements = {
        '{subject}': endings['subject'],
        '{verb_action}': endings['verb_action'],
        '{verb_started}': endings['verb_started'],
        '{adjective}': endings['adjective'],
        '{person}': endings['person'],
        '{pronoun}': endings['pronoun'],
    }
    
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    
    return text
# ========== УТИЛИТЫ ДЛЯ РАССЫЛКИ ==========

async def get_users_for_task_sending():
    """Возвращает пользователей для отправки заданий"""
    users = await get_all_users()
    if not users:  # Проверяем что users не None
        return []
    
    result = []
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            if not user_data:  # Проверяем что user_data не None
                continue
                
            # Если пользователь в спринте - отправляем задания
            if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
                if await can_receive_new_task(user_data):
                    result.append((user_id, user_data))
            # Логика для подписок
            elif await is_subscription_active(user_data) or await is_in_trial_period(user_data):
                if await can_receive_new_task(user_data):
                    result.append((user_id, user_data))
        except Exception as e:
            logger.error(f"❌ Ошибка обработки пользователя {user_id_str}: {e}")
    
    return result

async def get_users_without_response():
    """Возвращает пользователей, которые не ответили на сегодняшнее задание"""
    users = await get_all_users()
    if not users:  # Проверяем что users не None
        return []
    
    result = []
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            if not user_data:  # Проверяем что user_data не None
                continue
                
            if (await is_subscription_active(user_data) or await is_in_trial_period(user_data)):
                # Пользователь получил задание, но не ответил
                if (user_data.get('last_task_sent') and 
                    not user_data.get('task_completed_today')):
                    result.append((user_id, user_data))
        except Exception as e:
            logger.error(f"❌ Ошибка обработки пользователя {user_id_str}: {e}")
    
    return result

# ========== ДРУГИЕ УТИЛИТЫ ==========

async def get_user_timezone(user_id):
    """Возвращает часовой пояс пользователя"""
    user_data = await get_user(user_id)
    if user_data:
        return user_data.get('timezone', 'Europe/Moscow')
    return 'Europe/Moscow'