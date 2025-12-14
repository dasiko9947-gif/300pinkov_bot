import json
from venv import logger
import aiofiles
import random
import string
from datetime import datetime, timedelta
import config
import logging
# Базовые функции работы с файлами
async def read_json(file_path):
    """Асинхронно читает JSON файл"""
    try:
        if not file_path.exists():
            return {}
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content) if content else {}
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {}

async def write_json(file_path, data):
    """Асинхронно записывает данные в JSON файл"""
    try:
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error writing {file_path}: {e}")

# Функции работы с пользователями
async def get_user(user_id):
    users = await read_json(config.USERS_FILE)
    return users.get(str(user_id))

async def save_user(user_id, user_data):
    users = await read_json(config.USERS_FILE)
    users[str(user_id)] = user_data
    await write_json(config.USERS_FILE, users)

async def get_all_users():
    return await read_json(config.USERS_FILE)

async def update_user_activity(user_id):
    user_data = await get_user(user_id)
    if user_data:
        user_data['last_activity'] = datetime.now().isoformat()
        await save_user(user_id, user_data)

# Функции работы с заданиями
async def get_all_tasks():
    return await read_json(config.TASKS_FILE)

async def get_task_by_day(day_number, archetype="spartan"):
    """Ищет задание по дню и архетипу"""
    tasks = await get_all_tasks()
    
    # Сначала ищем точное совпадение по дню и архетипу
    for task_id, task in tasks.items():
        task_day = task.get('day_number')
        task_arch = task.get('archetype')
        
        if task_day == day_number and task_arch == archetype:
            return task_id, task
    
    # Если не нашли, ищем задание без архетипа (общее)
    for task_id, task in tasks.items():
        task_day = task.get('day_number')
        task_arch = task.get('archetype')
        
        if task_day == day_number and task_arch is None:
            return task_id, task
    
    # Если все еще не нашли, ищем любое задание этого дня
    for task_id, task in tasks.items():
        task_day = task.get('day_number')
        
        if task_day == day_number:
            return task_id, task
    
    return None, None

# Функции подписки
async def is_subscription_active(user_data):
    if not user_data or not user_data.get('subscription_end'):
        return False
    try:
        sub_end = datetime.fromisoformat(user_data['subscription_end'])
        return datetime.now() < sub_end
    except:
        return False

async def add_subscription_days(user_data, days):
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
    """Проверяет, находится ли пользователь в пробном периоде (первые 3 дня)"""
    if not user_data or not user_data.get('created_at'):
        return False
    
    try:
        created_at = datetime.fromisoformat(user_data['created_at'])
        days_passed = (datetime.now() - created_at).days
        return days_passed < 3  # Пробный период - первые 3 дня
    except:
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

# НОВАЯ СИСТЕМА РАНГОВ И ДОЛГОВ
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
    """Возвращает информацию о ранге с привилегиями только если ранг достигнут"""
    rank_info = config.RANKS.get(rank_id, {}).copy()
    
    return rank_info

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

# Отложенные задания

async def postpone_task(user_data):
    """Откладывает текущее задание в конец очереди"""
    postponed_tasks = user_data.get('postponed_tasks', [])
    current_day = user_data.get('current_day', 0) + 1
    
    # Проверяем лимит отложенных заданий
    if len(postponed_tasks) >= config.MAX_POSTPONED_TASKS:
        return user_data, False  # Нельзя отложить больше лимита
    
    # Добавляем задание в список отложенных
    postponed_task = {
        'day': current_day,
        'postponed_date': datetime.now().isoformat(),
        'completed': False
    }
    postponed_tasks.append(postponed_task)
    user_data['postponed_tasks'] = postponed_tasks
    
    # Увеличиваем счетчик текущего дня (пользователь переходит к следующему заданию)
    user_data['current_day'] = current_day
    user_data['task_completed_today'] = True
    
    return user_data, True

# В utils.py обновим функцию

async def complete_postponed_task(user_data):
    """Отмечает самое старое отложенное задание как выполненное"""
    postponed_tasks = user_data.get('postponed_tasks', [])
    if not postponed_tasks:
        return user_data
    
    # Находим первое невыполненное отложенное задание
    for task in postponed_tasks:
        if not task.get('completed', False):
            task['completed'] = True
            task['completed_date'] = datetime.now().isoformat()
            break
    
    user_data['postponed_tasks'] = postponed_tasks
    return user_data

async def get_current_postponed_count(user_data):
    """Возвращает количество текущих отложенных заданий"""
    postponed_tasks = user_data.get('postponed_tasks', [])
    active_postponed = [task for task in postponed_tasks if not task.get('completed', False)]
    return len(active_postponed)

async def get_todays_tasks(user_data):
    """Возвращает задание на сегодня - ОБНОВЛЕННАЯ ВЕРСИЯ"""
    tasks = []
    
    # Проверяем, может ли пользователь получать задания
    has_access = (
        await is_subscription_active(user_data) or 
        await is_in_trial_period(user_data) or
        (user_data.get('sprint_type') and not user_data.get('sprint_completed'))
    )
    
    if not has_access:
        return tasks
    
    # Проверяем, выполнено ли уже сегодняшнее задание
    if user_data.get('task_completed_today'):
        return tasks
    
    # Основное задание
    current_day = user_data.get('current_day', 0) + 1
    task_id, task = await get_task_by_day(current_day, user_data.get('archetype', 'spartan'))
    
    if task:
        # УНИФИЦИРОВАННАЯ СТРУКТУРА ДАННЫХ С ФЛАГОМ ЭТАПА
        task_data = {
            'type': 'main',
            'day': current_day,
            'task_id': task_id,
            'text': task.get('text', 'Текст задания не найден'),
            'data': task,  # Сохраняем оригинальные данные
            'is_new_stage': await should_send_stage_notification(user_data, current_day)  # ФЛАГ НОВОГО ЭТАПА
        }
        tasks.append(task_data)
    
    return tasks

async def get_postponed_tasks_after_300(user_data):
    """Возвращает отложенные задания после завершения 300 дней"""
    tasks = []
    
    # Проверяем, завершил ли пользователь 300 дней
    completed_tasks = user_data.get('completed_tasks', 0)
    if completed_tasks < 300:
        return tasks
    
    # Получаем отложенные задания
    postponed_tasks = user_data.get('postponed_tasks', [])
    active_postponed = [task for task in postponed_tasks if not task.get('completed', False)]
    
    # Сортируем по дате откладывания (самые старые первыми)
    active_postponed.sort(key=lambda x: x.get('postponed_date', ''))
    
    for i, postponed_task in enumerate(active_postponed, 1):
        postponed_day = postponed_task['day']
        postponed_task_id, task_data = await get_task_by_day(postponed_day, user_data['archetype'])
        if task_data:
            tasks.append({
                'type': 'postponed',
                'day': 300 + i,  # Отложенные становятся 300+n
                'original_day': postponed_day,
                'text': task_data['text'],
                'task_id': postponed_task_id,
                'postponed_date': postponed_task.get('postponed_date')
            })
    
    return tasks

# В utils.py обновим функцию

async def get_next_postponed_task(user_data):
    """Возвращает следующее отложенное задание после 300-го дня"""
    postponed_tasks = await get_postponed_tasks_after_300(user_data)
    
    if postponed_tasks:
        task = postponed_tasks[0]
        return {
            'type': 'postponed_final',
            'day': task['day'],
            'text': task['text'],
            'task_id': task['task_id'],
            'postponed_date': task.get('postponed_date'),
            'original_day': task.get('original_day')
        }
    
    return None

async def has_postponed_tasks_after_300(user_data):
    """Проверяет, есть ли отложенные задания после 300-го дня"""
    postponed_tasks = await get_postponed_tasks_after_300(user_data)
    return len(postponed_tasks) > 0
# Функции для спринта
async def start_detox_sprint(user_data):
    """Начинает 4-дневный спринт цифрового детокса"""
    user_data['sprint_type'] = 'detox'
    user_data['sprint_day'] = 1
    user_data['sprint_started'] = datetime.now().isoformat()
    user_data['sprint_completed'] = False
    user_data['last_task_sent'] = datetime.now().isoformat()
    user_data['task_completed_today'] = False
    return user_data

async def complete_detox_sprint(user_data):
    """Завершает спринт и предлагает продолжить"""
    user_data['current_day'] = 4  # 4/300 дней
    user_data['completed_tasks'] = 4  # Добавляем выполненные задания
    user_data['sprint_completed'] = True
    user_data['sprint_type'] = None
    user_data['sprint_day'] = None
    user_data['awaiting_trial_payment'] = True  # Флаг ожидания оплаты пробного периода
    
    # Обновляем ранг после спринта
    await update_user_rank(user_data)
    
    return user_data

async def get_sprint_task(day_number):
    """Возвращает задание для 4-дневного спринта"""
    sprint_tasks = {
        1: "Удали 10 ненужных чатов и отпишись от 5 пабликов/каналов, которые не несут пользы",
        2: "Выключи ВСЕ уведомления в телефоне, кроме звонков и сообщений от самых близких",
        3: "Поставь на телефоне ЧЕРНО-БЕЛЫЙ ФИЛЬТР (оттенки серого) на весь день", 
        4: "Все приемы пищи сегодня без телефона + вечером выключи телефон на 1 час"
    }
    return sprint_tasks.get(day_number)

async def can_receive_new_task(user_data):
    """Проверяет, может ли пользователь получить новое задание"""
    # Если пользователь в спринте - всегда может получить задание
    if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
        return True
    
    # Если пользователь еще не получал заданий
    if not user_data.get('last_task_sent'):
        return True
    
    # Если пользователь уже выполнил/пропустил сегодняшнее задание
    if user_data.get('task_completed_today'):
        return True
    
    # Проверяем, не прошло ли уже 24 часа с момента отправки последнего задания
    try:
        last_sent = datetime.fromisoformat(user_data['last_task_sent'])
        time_diff = datetime.now() - last_sent
        return time_diff.total_seconds() >= 24 * 3600  # 24 часа
    except:
        return True

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
    """Определяет уровень реферальной системы"""
    # Сначала проверяем высшие уровни
    levels = list(config.REFERRAL_LEVELS.items())
    levels.sort(key=lambda x: x[1]['min_refs'], reverse=True)
    
    for level_id, level_info in levels:
        if ref_count >= level_info['min_refs']:
            return level_id, level_info
    
    # Если не нашли, возвращаем начальный уровень
    return "putnik", config.REFERRAL_LEVELS["putnik"]

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

# Инвайт-коды
async def generate_invite_code(length=8):
    return ''.join(random.choice(string.digits) for _ in range(length))

async def create_invite_code(code_type="month", days=None, max_uses=1, created_by=None, pair_owner=None):
    """Создает инвайт-код БЕЗ параметров пинка"""
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
    """Активация инвайт-кода - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
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
    
    # ПРОВЕРЯЕМ ИСПОЛЬЗОВАНИЕ ПЕРЕД ЛЮБЫМИ ИЗМЕНЕНИЯМИ
    used_by = invite.get('used_by', [])
    
    # Проверяем, использовал ли пользователь уже этот код (по ID)
    if str(user_id) in [str(uid) for uid in used_by]:
        return False, "❌ Вы уже использовали этот код"
    
    # Проверяем лимит использований (по количеству использований)
    if invite['used_count'] >= invite['max_uses']:
        # Помечаем код как неактивный только если он достиг лимита
        invite['is_active'] = False
        await write_json(config.INVITE_CODES_FILE, invite_codes)
        return False, "❌ Код уже использован"
    
    # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - АКТИВИРУЕМ КОД
    invite['used_count'] += 1
    if 'used_by' not in invite:
        invite['used_by'] = []
    invite['used_by'].append(user_id)
    invite['last_used'] = datetime.now().isoformat()
    
    # Для одноразовых кодов деактивируем сразу после использования
    if invite['max_uses'] == 1:
        invite['is_active'] = False
    
    # ОДНОКРАТНОЕ СОХРАНЕНИЕ
    await write_json(config.INVITE_CODES_FILE, invite_codes)
    
    return True, invite

async def get_all_invite_codes(include_hidden=False):
    """Возвращает все инвайт-коды (по умолчанию скрытые не включаются)"""
    invite_codes = await read_json(config.INVITE_CODES_FILE)
    
    if not include_hidden:
        # Фильтруем скрытые коды (пинки)
        return {code: data for code, data in invite_codes.items() 
                if not data.get('is_hidden', False)}
    
    return invite_codes

# Часовые пояса
async def get_user_timezone(user_id):
    """Возвращает часовой пояс пользователя"""
    user_data = await get_user(user_id)
    if user_data:
        return user_data.get('timezone', 'Europe/Moscow')
    return 'Europe/Moscow'
async def get_privilege_links(rank_id, privilege_text):
    """Возвращает ссылку для конкретной привилегии"""
    links = config.PRIVILEGE_LINKS.get(rank_id, {})
    return links.get(privilege_text, None)

# Привилегии рангов
async def get_privileges_with_links(rank_id, user_data=None):
    """Возвращает привилегии с ссылками для текущего ранга"""
    rank_info = config.RANKS.get(rank_id, {})
    privileges = rank_info.get('privileges', [])
    
    result = []
    for privilege in privileges:
        # Всегда получаем ссылку из конфига
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
                # Если есть доступ и есть ссылка - показываем с ссылкой
                display_privileges.append(f"• {privilege}")
            elif has_access:
                # Если есть доступ, но нет ссылки - просто текст
                display_privileges.append(f"• {privilege}")
            else:
                # Если нет доступа - показываем заблокированным
                display_privileges.append(f"• 🔒 {privilege} (откроется после достижения)")
        
        rank_info['display_privileges'] = display_privileges
        rank_info['has_access'] = has_access
    else:
        rank_info['display_privileges'] = [f"• {p}" for p in rank_info.get('privileges', [])]
        rank_info['has_access'] = False
    
    return rank_info


async def get_stage_info_by_day(day_number):
    """Возвращает информацию о этапе по номеру дня"""
    stages = await read_json(config.STAGES_FILE)
    
    for stage_id, stage_data in stages.items():
        stage_start = stage_data.get('stage_day_start', 0)
        stage_end = stage_data.get('stage_day_end', 0)
        
        if stage_start <= day_number <= stage_end:
            return stage_data
    
    return None

async def get_stage_message_for_user(day_number, archetype):
    """Возвращает сообщение о этапе для пользователя"""
    stage_info = await get_stage_info_by_day(day_number)
    
    if not stage_info:
        return None
    
    # Получаем текст для конкретного архетипа
    if archetype == "spartan":
        stage_data = stage_info.get('spartan', {})
    else:
        stage_data = stage_info.get('amazon', {})
    
    if not stage_data:
        return None
    
    message = (
        f"<b>{stage_data.get('title', '')}</b>\n\n"
        f"<i>{stage_data.get('subtitle', '')}</i>\n\n"
        f"{stage_data.get('text', '')}\n\n"
        f"🔹 Этап: {stage_info.get('stage_name', '')}\n"
        f"🔹 Дни: {stage_info.get('stage_day_start', 0)}-{stage_info.get('stage_day_end', 0)}"
    )
    
    return message

async def should_send_stage_notification(user_data, next_day):
    """Проверяет, нужно ли отправлять уведомление о новом этапе"""
    try:
        current_day = user_data.get('current_day', 0)
        
        # Если это первый день (после сброса прогресса)
        if current_day == 0 and next_day == 1:
            return True  # Всегда показываем 1 этап в начале
        
        # Получаем информацию о текущем и следующем этапах
        current_stage = await get_stage_info_by_day(current_day)
        next_stage = await get_stage_info_by_day(next_day)
        
        # Если следующий день в новом этапе и это не тот же этап
        if next_stage and current_stage:
            if next_stage.get('stage_number') != current_stage.get('stage_number'):
                return True
        
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке уведомления о этапе: {e}")
        return False
# Утилиты для заданий
async def get_users_for_task_sending():
    """Возвращает пользователей для отправки заданий"""
    users = await get_all_users()
    result = []
    
    for user_id, user_data in users.items():
        # Если пользователь в спринте - отправляем задания
        if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
            if await can_receive_new_task(user_data):
                result.append((int(user_id), user_data))
        # Существующая логика для подписок
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

   

    """Возвращает задание для 4-дневного спринта"""
    sprint_tasks = {
        1: "Удали 10 ненужных чатов и отпишись от 5 пабликов/каналов, которые не несут пользы",
        2: "Выключи ВСЕ уведомления в телефоне, кроме звонков и сообщений от самых близких",
        3: "Поставь на телефоне ЧЕРНО-БЕЛЫЙ ФИЛЬТР (оттенки серого) на весь день", 
        4: "Все приемы пищи сегодня без телефона + вечером выключи телефон на 1 час"
    }
    return sprint_tasks.get(day_number)
    """Возвращает задание для 4-дневного спринта"""
    sprint_tasks = {
        1: "Удали 10 ненужных чатов и отпишись от 5 пабликов/каналов, которые не несут пользы",
        2: "Выключи ВСЕ уведомления в телефоне, кроме звонков и сообщений от самых близких",
        3: "Поставь на телефоне ЧЕРНО-БЕЛЫЙ ФИЛЬТР (оттенки серого) на весь день", 
        4: "Все приемы пищи сегодня без телефона + вечером выключи телефон на 1 час"
    }
    return sprint_tasks.get(day_number)
    """Проверяет, может ли пользователь получить новое задание"""
    # Если пользователь в спринте - всегда может получить задание
    if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
        return True
    
    # Остальная существующая логика...
    if not user_data.get('last_task_sent'):
        return True
    
    if user_data.get('task_completed_today'):
        return True
    
    try:
        last_sent = datetime.fromisoformat(user_data['last_task_sent'])
        time_diff = datetime.now() - last_sent
        return time_diff.total_seconds() >= 24 * 3600
    except:
        return True
    """Проверяет, может ли пользователь получить новое задание"""
    # Если пользователь еще не получал заданий
    if not user_data.get('last_task_sent'):
        return True
    
    # Если пользователь уже выполнил/пропустил сегодняшнее задание
    if user_data.get('task_completed_today'):
        return True
    
    # Проверяем, не прошло ли уже 24 часа с момента отправки последнего задания
    try:
        last_sent = datetime.fromisoformat(user_data['last_task_sent'])
        time_diff = datetime.now() - last_sent
        return time_diff.total_seconds() >= 24 * 3600  # 24 часа
    except:
        return True
# Утилиты для заданий

    """Возвращает пользователей для отправки заданий"""
    users = await get_all_users()
    result = []
    
    for user_id, user_data in users.items():
        if await is_subscription_active(user_data) or await is_in_trial_period(user_data):
            result.append((int(user_id), user_data))
    
    return result