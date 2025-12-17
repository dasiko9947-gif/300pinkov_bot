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
        return None, None
    
    # ФОРМАТ: "task_1_spartan"
    task_key = f"task_{day_number}_{archetype}"
    logger.info(f"🔑 Ищу задание по ключу: {task_key}")
    
    if task_key in tasks:
        task = tasks[task_key]
        logger.info(f"✅ Найдено задание: {task_key}")
        return task_key, task
    
    logger.warning(f"⚠️ Задание дня {day_number} для архетипа {archetype} не найдено")
    
    # Для отладки показываем первые 5 ключей
    available_keys = list(tasks.keys())[:5]
    logger.info(f"📋 Первые 5 ключей в файле: {available_keys}")
    
    return None, None

async def get_todays_tasks(user_data):
    """Возвращает задание на сегодня"""
    logger.info(f"🔍 get_todays_tasks: проверяю пользователя")
    logger.info(f"   Текущий день: {user_data.get('current_day', 0)}")
    logger.info(f"   Архетип: {user_data.get('archetype')}")
    
    tasks = []
    
    # Проверяем, может ли пользователь получать задания
    has_access = (
        await is_subscription_active(user_data) or 
        await is_in_trial_period(user_data)
    )
    
    if not has_access:
        logger.info(f"   ❌ Нет доступа к заданиям")
        return tasks
    
    # Проверяем, выполнено ли уже сегодняшнее задание
    if user_data.get('task_completed_today'):
        logger.info(f"   ⏸️ Задание уже выполнено сегодня")
        return tasks
    
    # Основное задание
    current_day = user_data.get('current_day', 0)
    next_day = current_day + 1
    
    logger.info(f"   📅 Следующий день: {next_day}")
    
    task_id, task = await get_task_by_day(next_day, user_data.get('archetype', 'spartan'))
    
    if task:
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
    
    logger.info(f"   📊 Всего заданий: {len(tasks)}")
    return tasks

async def can_receive_new_task(user_data):
    """Проверяет, может ли пользователь получить новое задание"""
    logger.info(f"🔍 can_receive_new_task: проверяю пользователя")
    
    # Если пользователь в спринте - всегда может получить задание
    if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
        logger.info(f"   ✅ В спринте - может получить задание")
        return True
    
    # Если задание уже выполнено сегодня - проверяем дату
    if user_data.get('task_completed_today', False):
        last_task_sent = user_data.get('last_task_sent')
        
        # ЕСЛИ last_task_sent НЕТ - это ошибка данных
        if not last_task_sent:
            logger.warning(f"⚠️ Противоречие: task_completed_today=True, но last_task_sent=None")
            return True  # Разрешаем чтобы исправить ситуацию
        
        try:
            # Проверяем, когда было последнее задание
            last_date = datetime.fromisoformat(last_task_sent).date()
            today = datetime.now().date()
            
            # Если задание было вчера или раньше - можем получить новое
            if last_date < today:
                logger.info(f"✅ Задание выполнено вчера, можно получить новое")
                return True
            else:
                logger.info(f"⏸️ Задание уже выполнено сегодня")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки даты: {e}")
            return True
    
    # Проверяем подписку и пробный период
    has_subscription = await is_subscription_active(user_data)
    in_trial = await is_in_trial_period(user_data)
    
    logger.info(f"   Подписка: {has_subscription}, Пробный: {in_trial}")
    
    if not has_subscription and not in_trial:
        logger.info(f"❌ Нет доступа к заданиям")
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
    """Проверяет активна ли подписка"""
    if not user_data or not user_data.get('subscription_end'):
        return False
    try:
        sub_end = datetime.fromisoformat(user_data['subscription_end'])
        return datetime.now() < sub_end
    except:
        return False

async def add_subscription_days(user_data, days):
    """Добавляет дни подписки"""
    if not user_data:
        user_data = {}
        
    if user_data.get('subscription_end'):
        try:
            current_end = datetime.fromisoformat(user_data['subscription_end'])
            if current_end > datetime.now():
                new_end = current_end + timedelta(days=days)
            else:
                new_end = datetime.now() + timedelta(days=days)
        except:
            new_end = datetime.now() + timedelta(days=days)
    else:
        new_end = datetime.now() + timedelta(days=days)
    
    user_data['subscription_end'] = new_end.isoformat()
    return user_data

async def is_in_trial_period(user_data):
    """Проверяет, находится ли пользователь в пробном периоде (3 дня)"""
    created_at_str = user_data.get('created_at')
    if not created_at_str:
        return False
    
    try:
        created_at = datetime.fromisoformat(created_at_str)
        days_passed = (datetime.now() - created_at).days
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

async def get_referral_level(ref_count):
    """Определяет уровень реферальной системы"""
    # Сначала проверяем высшие уровни
    levels = list(config.REFERRAL_LEVELS.items())
    levels.sort(key=lambda x: x[1]['min_refs'], reverse=True)
    
    for level_id, level_info in levels:
        if ref_count >= level_info['min_refs']:
            return level_id, level_info
    
    # Если не нашли, возвращаем начальный уровень (Легионер с 0 рефералов)
    return "legioner", config.REFERRAL_LEVELS["legioner"]

async def add_referral(referrer_id, referred_id):
    """Добавляет реферала"""
    referrer_data = await get_user(referrer_id)
    if referrer_data:
        referrals = referrer_data.get('referrals', [])
        if referred_id not in referrals:
            referrals.append(referred_id)
            referrer_data['referrals'] = referrals
            await save_user(referrer_id, referrer_data)
            return True
    return False

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

# ========== УТИЛИТЫ ДЛЯ РАССЫЛКИ ==========

async def get_users_for_task_sending():
    """Возвращает пользователей для отправки заданий"""
    users = await get_all_users()
    result = []
    
    for user_id, user_data in users.items():
        # Если пользователь в спринте - отправляем задания
        if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
            if await can_receive_new_task(user_data):
                result.append((int(user_id), user_data))
        # Логика для подписок
        elif await is_subscription_active(user_data) or await is_in_trial_period(user_data):
            if await can_receive_new_task(user_data):
                result.append((int(user_id), user_data))
    
    return result

async def get_users_without_response():
    """Возвращает пользователей, которые не ответили на сегодняшнее задание"""
    users = await get_all_users()
    result = []
    
    for user_id, user_data in users.items():
        if (await is_subscription_active(user_data) or await is_in_trial_period(user_data)):
            # Пользователь получил задание, но не ответил
            if (user_data.get('last_task_sent') and 
                not user_data.get('task_completed_today')):
                result.append((int(user_id), user_data))
    
    return result

# ========== ДРУГИЕ УТИЛИТЫ ==========

async def get_user_timezone(user_id):
    """Возвращает часовой пояс пользователя"""
    user_data = await get_user(user_id)
    if user_data:
        return user_data.get('timezone', 'Europe/Moscow')
    return 'Europe/Moscow'