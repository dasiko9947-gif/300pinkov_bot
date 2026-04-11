import asyncio
import logging
import payments
from datetime import datetime
import random
from aiogram import Bot, Dispatcher, F
from aiogram import exceptions
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
import keyboards
import config
import utils
import pytz
from utils import (
    get_user, save_user, update_user_activity, add_referral,
    is_subscription_active, is_in_trial_period, get_trial_days_left,
    update_user_rank, get_rank_info, get_referral_level, use_invite_code, add_subscription_days,
    get_all_users, start_detox_sprint, get_sprint_task
)

from keyboards import (
    get_main_menu, archetype_keyboard, task_keyboard, admin_keyboard,
    get_payment_keyboard, get_my_rank_keyboard, get_my_referral_keyboard,
    get_admin_invite_keyboard, get_invite_code_types_keyboard
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import exceptions
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
# В начале файла добавь новые состояния
class UserStates(StatesGroup):
    waiting_for_archetype = State()
    waiting_for_invite = State()
    waiting_for_timezone = State()  # Новое состояние
    waiting_for_ready = State()     # Новое состояние

# Инициализация планировщика
scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

# pyright: reportAttributeAccessIssue=false
# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def safe_edit_message(callback, text, reply_markup=None, parse_mode='HTML'):

    """Безопасно редактирует сообщение с обработкой ошибок"""
    try:
        if callback and callback.message:
            await callback.message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка редактирования сообщения: {e}")
        return False
async def safe_edit_reply_markup(callback, reply_markup):
    """Безопасно обновляет клавиатуру сообщения"""
    try:
        if callback and callback.message:
            await callback.message.edit_reply_markup(reply_markup=reply_markup)
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка обновления клавиатуры: {e}")
        return False

# Инициализация бота и диспетчера
if not config.BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в config.py")

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Мотивационные сообщения
HONESTY_MESSAGES = [
    "🎯 Помни: ты делаешь это для себя, а не для системы.",
    "💪 Честность перед собой - первый шаг к настоящим изменениям.",
    "🌟 Каждое выполненное задание - это инвестиция в себя.",
]
async def notify_referrer_about_bonus(referrer_id, bonus_info):
    """Отправляет уведомление рефереру о начисленном бонусе"""
    try:
        message_text = (
            f"🎉 <b>Реферальный бонус!</b>\n\n"
            f"Ваш реферал оплатил подписку!\n"
            f"Вам начислено: <b>{bonus_info['bonus_amount']} руб.</b>\n"
            f"Процент: {bonus_info['percent']}%\n"
            f"Сумма платежа: {bonus_info['payment_amount']} руб.\n\n"
            f"💎 Продолжайте приглашать друзей для увеличения дохода!"
        )
        
        await bot.send_message(
            chat_id=referrer_id,
            text=message_text
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления рефереру {referrer_id}: {e}")

async def safe_send_message(user_id, text, reply_markup=None, parse_mode='HTML'):
    """
    Безопасно отправляет сообщение с обработкой всех возможных ошибок
    """
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True  # ДОБАВИТЬ ЗДЕСЬ
        )
        logger.debug(f"✅ Сообщение отправлено пользователю {user_id}")
        return True
        
    except exceptions.BotBlocked:
        logger.warning(f"❌ Пользователь {user_id} заблокировал бота")
        return False
        
    except exceptions.ChatNotFound:
        logger.warning(f"❌ Чат с пользователем {user_id} не найден")
        return False
        
    except exceptions.UserDeactivated:
        logger.warning(f"❌ Пользователь {user_id} деактивирован")
        return False
        
    except exceptions.TelegramAPIError as e:
        logger.error(f"❌ Ошибка Telegram API для пользователя {user_id}: {e}")
        return False
        
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка отправки пользователю {user_id}: {e}")
        return False
# ========== СИСТЕМА РАССЫЛОК И НАПОМИНАНИЙ ==========

# Добавьте глобальную переменную для блокировки
is_sending_tasks = False

# В функции send_daily_tasks обновляем логику отправки

# В функции send_daily_tasks обновим логику отправки обычных заданий:

import asyncio
from aiogram import exceptions

async def send_daily_tasks():
    """ОПТИМИЗИРОВАННАЯ асинхронная рассылка заданий"""
    global is_sending_tasks
    
    if is_sending_tasks:
        logger.warning("⏸️ Рассылка уже выполняется, пропускаем дублирующий вызов")
        return
    
    is_sending_tasks = True
    logger.info("🕘 НАЧИНАЕМ ОПТИМИЗИРОВАННУЮ РАССЫЛКУ ЗАДАНИЙ")
    
    try:
        users = await utils.get_all_users()
        total_users = len(users)
        
        if total_users == 0:
            logger.info("👥 Нет пользователей для рассылки")
            return
        
        # Создаем задачи для асинхронной отправки
        tasks = []
        batch_size = 50  # Ограничиваем параллельные запросы
        
        for i, (user_id_str, user_data) in enumerate(users.items()):
            try:
                user_id = int(user_id_str)
                
                # Проверяем доступ к заданиям (быстрая проверка)
                has_subscription = await utils.is_subscription_active(user_data)
                in_trial = await utils.is_in_trial_period(user_data)
                in_sprint = user_data.get('sprint_type') and not user_data.get('sprint_completed')
                
                if not has_subscription and not in_trial and not in_sprint:
                    continue
                
                # Проверяем, может ли пользователь получить задание
                if not await utils.can_receive_new_task(user_data):
                    continue
                
                # Создаем задачу отправки
                task = send_task_to_user(user_id, user_data)
                tasks.append(task)
                
                # Отправляем батчами для контроля нагрузки
                if len(tasks) >= batch_size:
                    await process_batch(tasks, i, total_users)
                    tasks = []
                    await asyncio.sleep(1)  # Пауза между батчами
                    
            except Exception as e:
                logger.error(f"❌ Ошибка подготовки пользователя {user_id_str}: {e}")
        
        # Обрабатываем оставшиеся задачи
        if tasks:
            await process_batch(tasks, total_users, total_users)
        
        logger.info(f"✅ Оптимизированная рассылка завершена")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в оптимизированной рассылке: {e}")
        
    finally:
        is_sending_tasks = False

async def send_task_to_user(user_id: int, user_data: dict):
    """Отправляет задание конкретному пользователю"""
    try:
        # ЛОГИКА ОТПРАВКИ ЗАДАНИЙ (ваш существующий код)
        if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
            # Логика спринта
            sprint_day = user_data.get('sprint_day', 1)
            task_text = await utils.get_sprint_task(sprint_day)
            
            if task_text:
                message_text = (
                    f"⚡ <b>СПРИНТ: ДЕНЬ {sprint_day}/4</b>\n\n"
                    f"<b>Задание дня #{sprint_day}</b>\n\n"
                    f"{task_text}\n\n"
                    f"💪 Твой шаг к цифровой свободе!\n"
                    f"⏰ До 23:59 на выполнение\n\n"
                    f"<i>Встретимся завтра в 9:00 ⏰</i>"
                )
                
                await safe_send_message_optimized(
                    user_id=user_id,
                    text=message_text,
                    reply_markup=keyboards.task_keyboard
                )
                
                # Обновляем данные пользователя
                user_data['last_task_sent'] = datetime.now().isoformat()
                user_data['task_completed_today'] = False
                await utils.save_user(user_id, user_data)
                return True
                
        else:
            # ОБЫЧНЫЕ ЗАДАНИЯ
            todays_tasks = await utils.get_todays_tasks(user_data)
            
            if todays_tasks:
                task = todays_tasks[0]
                message_text = (
                    f"📋 <b>Задание на сегодня</b>\n\n"
                    f"<b>День {task['day']}/300</b>\n\n"
                    f"{task['text']}\n\n"
                    f"⏰ <b>До 23:59 на выполнение</b>\n\n"
                    f"<i>Встретимся завтра в 9:00 ⏰</i>"
                )
                
                await safe_send_message_optimized(
                    user_id=user_id,
                    text=message_text,
                    reply_markup=keyboards.task_keyboard
                )
                
                # Обновляем данные пользователя
                user_data['last_task_sent'] = datetime.now().isoformat()
                user_data['task_completed_today'] = False
                await utils.save_user(user_id, user_data)
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
        return False

async def process_batch(tasks: list, current: int, total: int):
    """Обрабатывает батч задач и логирует прогресс"""
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        logger.info(f"📦 Обработан батч: {success_count} успешно, {error_count} ошибок")
        logger.info(f"📊 Прогресс: {current}/{total} пользователей")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки батча: {e}")

async def safe_send_message_optimized(user_id: int, text: str, **kwargs):
    """Оптимизированная отправка сообщений с таймаутами"""
    try:
        await asyncio.wait_for(
            bot.send_message(user_id, text, **kwargs),
            timeout=10.0  # Таймаут 10 секунд
        )
        return True
        
    except asyncio.TimeoutError:
        logger.warning(f"⏰ Таймаут отправки пользователю {user_id}")
        return False
    except exceptions.BotBlocked:
        logger.info(f"🚫 Пользователь {user_id} заблокировал бота")
        return False
    except exceptions.ChatNotFound:
        logger.info(f"❓ Чат с пользователем {user_id} не найден")
        return False
    except exceptions.UserDeactivated:
        logger.info(f"💀 Пользователь {user_id} деактивирован")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
        return False

async def check_trial_expiry():
    """Проверяет и уведомляет пользователей об окончании пробного периода с кнопкой подписки"""
    logger.info("🔔 Проверяем окончание пробного периода...")
    
    users = await utils.get_all_users()
    notified_count = 0
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            
            # Пропускаем пользователей с активной подпиской
            if await utils.is_subscription_active(user_data):
                continue
            
            # Проверяем, закончился ли пробный период
            created_at = datetime.fromisoformat(user_data.get('created_at', datetime.now().isoformat()))
            days_passed = (datetime.now() - created_at).days
            
            # Если прошло ровно 3 дня - пробный период закончился
            if days_passed == 3:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                
                # Создаем клавиатуру с кнопкой подписки
                subscription_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="💎 Активировать подписку", 
                            callback_data="activate_subscription_after_trial"
                        )],
                        [InlineKeyboardButton(
                            text="📊 Мой прогресс", 
                            callback_data="show_progress_after_trial"
                        )]
                    ]
                )
                
                message_text = (
                    "🎯 <b>Ты прошел вводный этап!</b>\n\n"
                    "За 3 дня ты получил представление о том, как работает система «300 ПИНКОВ».\n\n"
                    "💪 <b>Что дальше?</b>\n"
                    "• Ежедневные задания для развития силы воли\n"
                    "• Система рангов и достижений\n" 
                    "• Поддержка комьюнити\n"
                    "• 297 дней роста впереди!\n\n"
                    "🔥 <b>Продолжи путь к сильной версии себя!</b>"
                )
                
                success = await safe_send_message(
                    user_id=user_id,
                    text=message_text,
                    reply_markup=subscription_keyboard
                )
                
                if success:
                    notified_count += 1
                    logger.info(f"✅ Уведомление отправлено пользователю {user_id}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка уведомления пользователя {user_id_str}: {e}")
    
    logger.info(f"📊 Уведомления отправлены: {notified_count} пользователям")

# В функции send_reminders обновим логику:

async def send_reminders():
    """Напоминания в 18:30 с информацией о долгах"""
    logger.info("🕡 Начинаем рассылку напоминаний...")
    
    users = await utils.get_users_without_response()
    sent_count = 0
    error_count = 0
    
    for user_id, user_data in users:
        try:
            # Получаем только основное задание
            todays_tasks = await utils.get_todays_tasks(user_data)
            
            if todays_tasks:
                task = todays_tasks[0]
                message_text = (
                    f"🎯 <b>ВРЕМЯ ДЕЙСТВОВАТЬ!</b>\n\n"
                    f"Вечер - идеальное время для завершения дня победой!\n\n"
                    f"<b>Задание дня #{task['day']}</b>\n"
                    f"«{task['text']}»\n\n"
                    f"Не упусти шанс сделать сегодняшний день значимым!\n"
                    f"Завтра ты поблагодаришь себя за эту маленькую победу.\n\n"
                    f"<i>До 23:59 на выполнение</i>"
                )
                
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=keyboards.task_keyboard,
                    disable_web_page_preview=True
                )
                
                sent_count += 1
                logger.info(f"✅ Напоминание отправлено пользователю {user_id}")
                
        except Exception as e:
            error_count += 1
            logger.error(f"❌ Ошибка напоминания пользователю {user_id}: {e}")
    
    logger.info(f"📊 Напоминания завершены: {sent_count} отправлено, {error_count} ошибок")
async def check_midnight_reset():
    """Полуночный сброс и блокировка неподтвержденных пользователей"""
    logger.info("🕛 Выполняем полуночный сброс...")
    
    users = await utils.get_all_users()
    reset_count = 0
    blocked_count = 0
    
    for user_id, user_data in users.items():
        try:
            # Сбрасываем флаг выполнения задания
            if user_data.get('task_completed_today'):
                user_data['task_completed_today'] = False
                reset_count += 1
            
            # Блокируем пользователей, которые не отметили вчерашнее задание
            if (user_data.get('last_task_sent') and 
                not user_data.get('task_completed_today') and
                await utils.is_subscription_active(user_data)):
                
                # Отправляем сообщение о блокировке
                message_text = (
                    f"⏸️ <b>ПАУЗА</b>\n\n"
                    f"Ты не отметил вчерашний вызов.\n\n"
                    f"Дисциплина требует последовательности!\n"
                    f"Вернись во вчерашнее сообщение и отметь «✅ Выполнил» или «⏭️ Пропустить» чтобы разблокировать новые задания.\n\n"
                    f"<i>Каждый пропущенный день - отложенная победа!</i>"
                )
                
                await bot.send_message(chat_id=int(user_id), text=message_text)
                blocked_count += 1
                
        except Exception as e:
            logger.error(f"❌ Ошибка сброса пользователя {user_id}: {e}")
    
    logger.info(f"📊 Сброс завершен: {reset_count} сброшено, {blocked_count} заблокировано")
# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@dp.message(Command("check_duplicates"))
async def check_duplicates_command(message: Message):
    """Проверка пользователей с возможными дубликатами заданий"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    users = await utils.get_all_users()
    problem_users = []
    
    for user_id, user_data in users.items():
        if user_data.get('last_task_sent'):
            try:
                last_sent = datetime.fromisoformat(user_data['last_task_sent'])
                today = datetime.now().date()
                last_sent_date = last_sent.date()
                
                # Если задание отправлено сегодня, но не выполнено - возможный дубликат
                if last_sent_date == today and not user_data.get('task_completed_today'):
                    problem_users.append((user_id, user_data))
            except:
                pass
    
    if problem_users:
        report = f"⚠️ <b>Найдено пользователей с возможными дубликатами: {len(problem_users)}</b>\n\n"
        for user_id, user_data in problem_users[:10]:  # Показываем первые 10
            report += f"👤 {user_data.get('first_name', 'User')} (ID: {user_id})\n"
        
        if len(problem_users) > 10:
            report += f"\n... и еще {len(problem_users) - 10} пользователей"
    else:
        report = "✅ Проблем с дубликатами не найдено"
    
    await message.answer(report)
@dp.message(Command("debug_tasks"))
async def debug_tasks_command(message: Message):
    """Отладочная информация о заданиях"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    # Получаем все задания
    all_tasks = await utils.get_all_tasks()
    
    # Текущий день пользователя
    current_day = user_data.get('current_day', 0) + 1
    archetype = user_data.get('archetype', 'spartan')
    
    # Ищем задание для текущего дня
    task_id, task = await utils.get_task_by_day(current_day, archetype)
    
    debug_info = (
        f"🔧 <b>ОТЛАДОЧНАЯ ИНФОРМАЦИЯ</b>\n\n"
        f"👤 <b>Пользователь:</b>\n"
        f"• ID: {user_id}\n"
        f"• Текущий день: {user_data.get('current_day', 0)}\n"
        f"• Следующий день: {current_day}\n"
        f"• Архетип: {archetype}\n\n"
        f"📊 <b>Задания в базе:</b>\n"
        f"• Всего заданий: {len(all_tasks)}\n"
        f"• Найдено для дня {current_day}: {'ДА' if task else 'НЕТ'}\n\n"
    )
    
    # Показываем задания для этого дня и архетипа
    matching_tasks = []
    for task_key, task_data in all_tasks.items():
        if task_data.get('day_number') == current_day and task_data.get('archetype') == archetype:
            matching_tasks.append(task_data)
    
    debug_info += f"<b>Задания для дня {current_day} ({archetype}):</b> {len(matching_tasks)}\n"
    
    for i, task_data in enumerate(matching_tasks):
        debug_info += f"{i+1}. {task_data.get('text', '')}\n"
    
    if not matching_tasks:
        debug_info += "\n❌ <b>Нет заданий для этого дня и архетипа!</b>"
    
    await message.answer(debug_info)
@dp.message(Command("create_test_tasks"))
async def create_test_tasks_command(message: Message):
    """Создание тестовых заданий"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    # Загружаем текущие задания
    tasks = await utils.get_all_tasks()
    
    # Добавляем тестовые задания для дней 1-10
    test_tasks = {
        "task_1_spartan": {
            "day_number": 1, "archetype": "spartan", 
            "text": "Сделай 20 отжиманий сразу после пробуждения",
            "created_at": datetime.now().isoformat(),
            "created_by": user.id
        },
        "task_1_amazon": {
            "day_number": 1, "archetype": "amazon",
            "text": "Сделай 15 приседаний сразу после пробуждения",
            "created_at": datetime.now().isoformat(),
            "created_by": user.id
        },
        "task_2_spartan": {
            "day_number": 2, "archetype": "spartan",
            "text": "Выпей стакан воды перед первым приемом пищи", 
            "created_at": datetime.now().isoformat(),
            "created_by": user.id
        },
        "task_2_amazon": {
            "day_number": 2, "archetype": "amazon",
            "text": "Сделай 5-минутную утреннюю растяжку",
            "created_at": datetime.now().isoformat(),
            "created_by": user.id
        },
        "task_3_spartan": {
            "day_number": 3, "archetype": "spartan",
            "text": "Откажись от сладкого на весь день",
            "created_at": datetime.now().isoformat(), 
            "created_by": user.id
        },
        "task_3_amazon": {
            "day_number": 3, "archetype": "amazon",
            "text": "Приготовь здоровый завтрак самостоятельно",
            "created_at": datetime.now().isoformat(),
            "created_by": user.id
        }
    }
    
    # Добавляем задания в базу
    tasks.update(test_tasks)
    
    # Сохраняем
    await utils.write_json(config.TASKS_FILE, tasks)
    
    await message.answer(f"✅ Создано {len(test_tasks)} тестовых заданий!")

@dp.message(Command("reset_me"))
async def reset_me_command(message: Message, state: FSMContext):
    """Полный сброс прогресса пользователя с очисткой состояний"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    
    # Загружаем текущих пользователей
    users = await utils.get_all_users()
    
    if str(user_id) not in users:
        await message.answer("❌ Пользователь не найден в базе данных")
        return
    
    # 1. Очищаем состояние FSM
    try:
        await state.clear()
    except:
        pass
    
    # 2. УДАЛЯЕМ пользователя из базы
    del users[str(user_id)]
    
    # 3. Сохраняем обновленную базу
    await utils.write_json(config.USERS_FILE, users)
    
    # 4. Очищаем возможные кэши (если они есть)
    try:
        # Если используете redis или другой кэш
        # await redis_client.delete(f"user:{user_id}")
        pass
    except:
        pass
    
    await message.answer(
        "🗑️ <b>ПОЛНЫЙ СБРОС И УДАЛЕНИЕ!</b>\n\n"
        "✅ <b>Все твои данные были удалены:</b>\n"
        "• Прогресс дней: сброшен\n" 
        "• Подписка: отменена\n"
        "• Ранг: сброшен\n"
        "• Рефералы: удалены\n"
        "• Все настройки: сброшены\n\n"
        "🔁 <b>Теперь можешь начать заново:</b>\n"
        "Просто снова используй команду /start\n\n"
        "Спасибо, что был с нами! 👋"
    )


@dp.message(Command("sprint_off"))
async def sprint_off_command(message: Message):
    """Команда для отключения спринта"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if user_data and user_data.get('sprint_type'):
        user_data['sprint_type'] = None
        user_data['sprint_day'] = None
        user_data['sprint_completed'] = True
        user_data['current_day'] = 4
        
        await utils.save_user(user_id, user_data)
        await message.answer(
            "🎯 <b>Спринт завершен досрочно!</b>\n\n"
            "Ты переходишь к основному челленджу 300 ПИНКОВ!\n\n"
            "Завтра в 9:00 получишь первое задание основного пути!",
            reply_markup=keyboards.get_main_menu(user_id)
        )
    else:
        await message.answer("❌ Спринт не активен.")

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start с улучшенной диагностикой"""
    user = message.from_user
    if not user:
        await message.answer("Ошибка: не удалось получить информацию о пользователе")
        return
        
    args = message.text.split() if message.text else []
    
    # Очищаем состояние на всякий случай
    try:
        await state.clear()
    except:
        pass
    
    user_data = await get_user(user.id)
    
    if user_data:
        # Пользователь уже зарегистрирован
        welcome_name = user.first_name or "Путник"
        await message.answer(
            f"С возвращением, {welcome_name}! 👋",
            reply_markup=get_main_menu(user.id)
        )
        await update_user_activity(user.id)
    else:
        # Новый пользователь - начинаем регистрацию
        await message.answer(
            "👋 <b>Добро пожаловать в челлендж «300 ПИНКОВ»!</b>\n\n"
            "• Этот бот не про мотивацию. Это <b>система</b>, которая заставляет мозг и тело работать по-новому. Как тренажёрный зал для привычек и мышления.\n\n"
            
            "🎯 <b>Что тебя ждет:</b>\n"
            "• Ежедневные задания для саморазвития\n"
            "• 300 дней непрерывного роста\n" 
            "• Система рангов и достижений\n\n"

            "💪 <b>Как это работает:</b>\n"
            "Каждый день в 9:00 ты получаешь ПИНОК.\n"
            "У тебя есть время до 23:59, чтобы его выполнить.\n"
            "Честность перед собой - главное правило!\n\n"
            "⬇️ <b>Давай настроим твой челлендж!</b>",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="➡️ Продолжить настройку")]],
                resize_keyboard=True
            )
        )
        await state.set_state(UserStates.waiting_for_timezone)
@dp.message(Command("force_reset"))
async def force_reset_command(message: Message, state: FSMContext):
    """Принудительный сброс пользователя (только для админа)"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    # Безопасная проверка message.text
    if not message.text:
        await message.answer("❌ Текст сообщения пуст")
        return
        
    # Парсим ID пользователя из команды: /force_reset 123456789
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /force_reset USER_ID")
        return
        
    try:
        target_user_id = int(args[1])
        
        # Загружаем текущих пользователей
        users = await utils.get_all_users()
        
        if str(target_user_id) not in users:
            await message.answer(f"❌ Пользователь {target_user_id} не найден в базе")
            return
            
        # Удаляем пользователя
        del users[str(target_user_id)]
        await utils.write_json(config.USERS_FILE, users)
        
        await message.answer(f"✅ Пользователь {target_user_id} принудительно сброшен")
        
    except ValueError:
        await message.answer("❌ Неверный ID пользователя")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
@dp.message(UserStates.waiting_for_timezone, F.text == "➡️ Продолжить настройку")
async def process_timezone_step(message: Message, state: FSMContext):
    """ШАГ 2: Выбор часового пояса"""
    from keyboards import get_timezone_keyboard  # Добавляем импорт здесь
    
    await message.answer(
        "🕐 <b>Выбери свой часовой пояс:</b>\n\n"
        "Это нужно чтобы задания приходили ровно в 9:00 по твоему местному времени.\n\n"
        "Просто нажми на кнопку с твоим городом или ближайшим к тебе часовым поясом:",
        reply_markup=get_timezone_keyboard()
    )

@dp.message(UserStates.waiting_for_timezone)
async def process_timezone_selection(message: Message, state: FSMContext):
    """Обработка выбора часового пояса"""
    timezone_map = config.RUSSIAN_TIMEZONES
    selected_timezone = None
    
    for tz_name, tz_value in timezone_map.items():
        if message.text and tz_name in message.text:
            selected_timezone = tz_value
            break
    
    if not selected_timezone:
        await message.answer("Пожалуйста, выбери часовой пояс:")
        return
    
    # Сохраняем часовой пояс в состоянии
    await state.update_data(timezone=selected_timezone)
    
    # ШАГ 3: Объяснение архетипов
    await message.answer(
        "💪 <b>Выбери свой путь развития</b>\n\n"
        "У нас два архетипа - каждый со своим стилем заданий:\n\n"
        "🛡️ <b>Амазонка</b>\n"
        "• Задания на осознанность и женскую энергию\n"
        "• Развитие интуиции и эмоционального интеллекта\n\n"
        "⚔️ <b>Спартанец</b>\n" 
        "• Задания на физическую и ментальную стойкость\n"
        "• Развитие лидерских качеств и ответственности\n\n"
        "🎯 <b>Общие принципы для всех:</b>\n"
        "• Честность перед собой - главное правило\n"
        "• Дисциплина создает мотивацию, а не наоборот\n"
        "• Каждый день - новое изменение\n\n"
        "Выбирай тот путь, который откликается тебе сильнее:",
        reply_markup=archetype_keyboard
    )
    await state.set_state(UserStates.waiting_for_archetype)

@dp.message(UserStates.waiting_for_archetype)
async def process_archetype_selection(message: Message, state: FSMContext):
    """ШАГ 4: Обработка выбора архетипа"""
    user = message.from_user
    if not user:
        await message.answer("Ошибка: не удалось получить информацию о пользователе")
        return
        
    if not message.text:
        await message.answer("Пожалуйста, выбери архетип с клавиатуры:")
        return
        
    archetype_map = {
        "⚔️ спартанец": "spartan",
        "🛡️ амазонка": "amazon"
    }
    
    archetype = None
    text_lower = message.text.lower()
    for key, value in archetype_map.items():
        if key in text_lower:
            archetype = value
            break
    
    if not archetype:
        await message.answer("Пожалуйста, выбери архетип с клавиатуры:")
        return
    
    # Сохраняем архетип в состоянии
    await state.update_data(archetype=archetype)
    
    # ШАГ 5: Финальное подтверждение
    from keyboards import get_ready_keyboard  # Добавляем импорт здесь
    
    archetype_name = "Спартанца" if archetype == "spartan" else "Амазонки"
    
    await message.answer(
        f"🎉 <b>Отличный выбор!</b>\n\n"
        f"Ты выбрал путь {archetype_name}!\n\n"
        f"⚠️ <b>Важное напоминание:</b>\n"
        f"• Задания приходят в 9:00 по твоему времени\n"
        f"• Время на выполнение до 23:59\n"
        f"• Честность перед собой - основа системы\n"
        f"• Пропуски превращаются в долги\n\n"
        f"💪 <b>Ты готов начать свой путь к сильной версии себя?</b>\n"
        f"Следующим сообщением ты получишь первое задание!",
        reply_markup=get_ready_keyboard()
    )
    await state.set_state(UserStates.waiting_for_ready)

@dp.message(UserStates.waiting_for_ready)
async def process_ready_confirmation(message: Message, state: FSMContext):
    """ШАГ 6: Обработка подтверждения готовности"""
    user = message.from_user
    if not user:
        await message.answer("Ошибка: не удалось получить информацию о пользователе")
        return
    
    if message.text == "❌ Нет, я передумал":
        await message.answer(
            "Хорошо, если захочешь измениться - всегда ждем тебя! 👋\n"
            "Просто снова нажми /start когда будешь готов.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        return
    
    if message.text != "✅ Да, я готов начать!":
        await message.answer("Пожалуйста, подтверди готовность кнопкой ниже:")
        return
    
    # Получаем все сохраненные данные
    user_data = await state.get_data()
    timezone = user_data.get('timezone', 'Europe/Moscow')
    archetype = user_data.get('archetype', 'spartan')
    
    # Создаем запись пользователя
    new_user_data = {
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "archetype": archetype,
        "timezone": timezone,  # Сохраняем часовой пояс
        "current_day": 0,
        "completed_tasks": 0,
        "rank": "putnik",
        "created_at": datetime.now().isoformat(),
        "referrals": [],
        "referral_earnings": 0,
        "last_task_sent": None,
        "task_completed_today": False,
        "debts": [],
        "last_activity": datetime.now().isoformat()
    }
    
    await save_user(user.id, new_user_data)
    
    # Отправляем первое задание (используем функцию из utils)
    task_id, task = await utils.get_task_by_day(1, archetype)
    
    if task:
        await message.answer(
            "🎯 <b>ТВОЕ ПЕРВОЕ ЗАДАНИЕ!</b>\n\n"
            f"<b>День 1/300</b>\n\n"
            f"{task['text']}\n\n"
            f"💪 Начало твоего пути к сильной версии себя!\n"
            f"⏰ У тебя есть время до 23:59 на выполнение\n\n"
            f"<i>Отмечай выполнение кнопками ниже 👇</i>",
            reply_markup=task_keyboard,
            disable_web_page_preview=True
        )
    else:
        await message.answer(
            "🎯 <b>Добро пожаловать в челлендж!</b>\n\n"
            "К сожалению, первое задание временно недоступно.\n"
            "Обратись к администратору или проверь позже.\n\n"
            "А пока можешь ознакомиться с функциями бота:",
            reply_markup=get_main_menu(user.id)
        )
    
    await message.answer(
        "📋 <b>Теперь тебе доступны все функции бота!</b>\n\n"
        "Используй меню ниже для навигации:",
        reply_markup=get_main_menu(user.id)
    )
    
    await state.clear()
    await update_user_activity(user.id)

@dp.message(UserStates.waiting_for_archetype)
async def process_archetype(message: Message, state: FSMContext):
    """Обработка выбора архетипа"""
    user = message.from_user
    if not user:
        await message.answer("Ошибка: не удалось получить информацию о пользователе")
        return
        
    if not message.text:
        await message.answer("Пожалуйста, выбери архетип с клавиатуры:")
        return
        
    archetype_map = {
        "⚔️ спартанец": "spartan",
        "🛡️ амазонка": "amazon"
    }
    
    archetype = None
    text_lower = message.text.lower()
    for key, value in archetype_map.items():
        if key in text_lower:
            archetype = value
            break
    
    if not archetype:
        await message.answer("Пожалуйста, выбери архетип с клавиатуры:")
        return
    
    user_data = {
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "archetype": archetype,
        "current_day": 0,
        "completed_tasks": 0,  # ДОБАВИТЬ ЭТУ СТРОКУ
        "rank": "putnik",
        "created_at": datetime.now().isoformat(),
        "referrals": [],
        "referral_earnings": 0,
        "last_task_sent": None,
        "task_completed_today": False,
        "debts": []  # ДОБАВИТЬ пустой список долгов
    }
    
    await save_user(user.id, user_data)
    
    if archetype == "spartan":
        welcome_text = "🛡️ <b>Путь Спартанца выбран!</b>\n\nТвой путь — сила, дисциплина и порядок."
    else:
        welcome_text = "⚔️ <b>Путь Амазонки выбран!</b>\n\nТвой путь — грация, сила и гармония."
    
    await message.answer(welcome_text, reply_markup=get_main_menu(user.id))
    await state.clear()
    await update_user_activity(user.id)

# В функции show_todays_task заменим логику:

# В функции show_todays_task заменим:

# ОБНОВЛЯЕМ обработчик для нового текста кнопки
@dp.message(F.text.contains("Задание на сегодня"))
async def show_todays_task(message: Message):
    """Улучшенный обработчик кнопки задания"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала зарегистрируйся через /start")
        return
    
    logger.info(f"👤 Пользователь {user_id} запросил задание")
    
    # Проверяем спринт
    if user_data.get('sprint_type') and not user_data.get('sprint_completed'):
        sprint_day = user_data.get('sprint_day', 1)
        task_text = await utils.get_sprint_task(sprint_day)
        
        if task_text:
            message_text = (
                f"⚡ <b>СПРИНТ: ДЕНЬ {sprint_day}/4</b>\n\n"
                f"<b>Задание дня #{sprint_day}</b>\n\n"
                f"{task_text}\n\n"
                f"💪 Твой шаг к цифровой свободе!\n"
                f"⏰ До 23:59 на выполнение"
            )
            await message.answer(message_text, reply_markup=keyboards.task_keyboard)
        else:
            await message.answer("❌ Задание спринта не найдено!")
        
        await utils.update_user_activity(user_id)
        return
    
    # Проверяем отложенные задания после 300 дней
    if await utils.has_postponed_tasks_after_300(user_data):
        postponed_task = await utils.get_next_postponed_task(user_data)
        if postponed_task:
            task_message = await format_postponed_task_message(postponed_task)
            await message.answer(
                task_message, 
                reply_markup=keyboards.task_keyboard,
                disable_web_page_preview=True
            )
            await utils.update_user_activity(user_id)
            return
    
    # Обычные задания
    todays_tasks = await utils.get_todays_tasks(user_data)
    
    if not todays_tasks:
        await message.answer(
            "🎉 <b>На сегодня заданий нет!</b>\n\n"
            "Возможно:\n"
            "• Ты уже выполнил сегодняшнее задание\n"
            "• Подписка не активна\n"
            "• Задание еще не пришло\n\n"
            "Проверь статус подписки или подожди до завтра!",
            reply_markup=keyboards.get_main_menu(user_id)
        )
        return
    
    # Отправляем основное задание
    for task in todays_tasks:
        task_message = await format_task_message(
            task['data'], 
            task['day'], 
            task['type']
        )
        await message.answer(
            task_message, 
            reply_markup=keyboards.task_keyboard,
            disable_web_page_preview=True
        )
    
    await utils.update_user_activity(user_id)

async def format_task_message(task_data, day, task_type):
    """Форматирует сообщение с заданием"""
    if task_type == 'postponed_final':
        return (
            f"📋 <b>ОТЛОЖЕННОЕ ЗАДАНИЕ</b>\n\n"
            f"<b>День {day}/300+</b>\n\n"
            f"{task_data['text']}\n\n"
            f"⏰ <b>Это задание было отложено ранее</b>\n"
            f"Выполни его чтобы продолжить!\n\n"
            f"<i>Время на выполнение: до 23:59</i>"
        )
    else:
        return (
            f"📋 <b>Задание на сегодня</b>\n\n"
            f"<b>День {day}/300</b>\n\n"
            f"{task_data['text']}\n\n"
            f"⏰ <b>До 23:59 на выполнение</b>\n\n"
            f"<i>Отмечай выполнение кнопками ниже 👇</i>"
        )

async def format_postponed_task_message(postponed_task):
    """Форматирует сообщение для отложенного задания"""
    return (
        f"📋 <b>ОТЛОЖЕННОЕ ЗАДАНИЕ</b>\n\n"
        f"<b>День {postponed_task['day']}/300+</b>\n\n"
        f"{postponed_task['text']}\n\n"
        f"⏰ <b>Это задание было отложено ранее</b>\n"
        f"Выполни его чтобы продолжить!\n\n"
        f"<i>Время на выполнение: до 23:59</i>"
    )

@dp.message(Command("debug_me"))
async def debug_me_command(message: Message):
    """Отладочная информация о пользователе"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Пользователь не найден в базе")
        return
    
    # Получаем сегодняшние задания
    todays_tasks = await utils.get_todays_tasks(user_data)
    postponed_tasks = await utils.get_postponed_tasks_after_300(user_data)
    
    debug_info = (
        f"🔧 <b>ОТЛАДОЧНАЯ ИНФОРМАЦИЯ</b>\n\n"
        f"👤 <b>Пользователь:</b>\n"
        f"• ID: {user_id}\n"
        f"• Текущий день: {user_data.get('current_day', 0)}\n"
        f"• Следующий день: {user_data.get('current_day', 0) + 1}\n"
        f"• Выполнено заданий: {user_data.get('completed_tasks', 0)}\n"
        f"• Архетип: {user_data.get('archetype', 'не установлен')}\n\n"
        f"📊 <b>Статус заданий:</b>\n"
        f"• Основных заданий сегодня: {len(todays_tasks)}\n"
        f"• Отложенных заданий: {len(postponed_tasks)}\n"
        f"• Задание выполнено сегодня: {user_data.get('task_completed_today', False)}\n"
        f"• Последнее задание отправлено: {user_data.get('last_task_sent', 'никогда')}\n\n"
        f"💎 <b>Подписка:</b>\n"
        f"• Активна: {await utils.is_subscription_active(user_data)}\n"
        f"• Пробный период: {await utils.is_in_trial_period(user_data)}\n"
        f"• В спринте: {user_data.get('sprint_type') and not user_data.get('sprint_completed')}\n"
    )
    
    await message.answer(debug_info)

# Обработчик активации инвайт-кода из нового раздела
@dp.callback_query(F.data == "activate_invite")
async def activate_invite_handler(callback: CallbackQuery, state: FSMContext):
    """Активация инвайт-кода из раздела Инвайт-коды"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    await callback.message.edit_text(
        "🎫 <b>Активация инвайт-кода</b>\n\n"
        "Введите инвайт-код для активации подписки:"
    )
    await state.set_state(UserStates.waiting_for_invite)

# НОВЫЙ обработчик подарка подписки
@dp.callback_query(F.data == "gift_subscription")
async def gift_subscription_handler(callback: CallbackQuery):
    """Подарок подписки другу"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    message_text = (
        "🎁 <b>ПОДАРОК ПОДПИСКИ ДРУГУ</b>\n\n"
        "Хочешь сделать подарок? Отличная идея! 🎉\n\n"
        "💎 <b>Доступные варианты подарков:</b>\n"
        "• 📅 Месячная подписка - 300 руб.\n"
        "• 🎯 Годовая подписка - 3000 руб.\n"
        "• 👥 Парная годовая - 5000 руб.\n\n"
        "🎫 <b>Как это работает:</b>\n"
        "1. Выбираешь тариф подписки\n"
        "2. Оплачиваешь через ЮKassa\n"
        "3. Получаешь инвайт-код\n"
        "4. Передаешь код другу\n"
        "5. Друг активирует подписку!\n\n"
        "Выбери тариф для подарка:"
    )
    
    # Используем ту же клавиатуру что и для обычной подписки
    await callback.message.edit_text(message_text, reply_markup=keyboards.get_payment_keyboard())
    await callback.answer()

# Обработчик реферальной программы из нового раздела
@dp.callback_query(F.data == "show_referral")
async def show_referral_from_legion(callback: CallbackQuery):
    """Показывает реферальную программу из раздела Мой легион"""
    if not callback or not callback.from_user:
        return
        
    if not callback.message:
        try:
            await callback.answer("Ошибка: сообщение не найдено", show_alert=True)
        except:
            pass
        return
        
    user_id = callback.from_user.id
    user_data = await get_user(user_id)
    
    if not user_data:
        try:
            await callback.answer("Сначала зарегистрируйся", show_alert=True)
        except:
            pass
        return
    
    referrals = user_data.get('referrals', [])
    earnings = user_data.get('referral_earnings', 0)
    ref_level_id, ref_level = await get_referral_level(len(referrals))
    
    message_text = (
        f"<b>РЕФЕРАЛЬНАЯ ПРОГРАММА 🤝</b>\n\n"
        f"💫 <b>Приглашай друзей и получай до 50% от их платежей!</b>\n\n"
        f"• Приглашено друзей: {len(referrals)}\n"
        f"• Заработано: {earnings} руб.\n"
        f"• Текущий уровень: {ref_level['name']}\n"
        f"• Ваш процент: {ref_level['percent']}%\n\n"
        f"📤 <b>Просто нажми кнопку ниже чтобы отправить приглашение!</b>"
    )
    
    try:
        await callback.message.edit_text(
            message_text, 
            reply_markup=keyboards.get_my_referral_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        try:
            await callback.answer("Не удалось обновить сообщение", show_alert=True)
        except:
            pass
    
    try:
        await callback.answer()
    except:
        pass
# Обработчик кнопки "⚔️ ВЫПОЛНИЛ" 
# В обработчике task_completed обновим логику:
@dp.message(F.text == "⚔️ ВЫПОЛНИЛ")
async def task_completed(message: Message):
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        return
    
    # Проверяем тип задания: основное или отложенное после 300 дней
    todays_tasks = await utils.get_todays_tasks(user_data)
    postponed_tasks = await utils.get_postponed_tasks_after_300(user_data)
    
    if not todays_tasks and not postponed_tasks:
        await message.answer("❌ Нет активных заданий для выполнения!")
        return
    
    if todays_tasks:
        # Основное задание
        current_task = todays_tasks[0]
        user_data['current_day'] = user_data.get('current_day', 0) + 1
        user_data['completed_tasks'] = user_data.get('completed_tasks', 0) + 1
        user_data['task_completed_today'] = True
        
        message_suffix = "\n\n🎉 <b>Отлично! Ты идеально справляешься!</b>"
            
    elif postponed_tasks:
        # Отложенное задание после 300 дней
        current_task = postponed_tasks[0]
        user_data = await utils.complete_postponed_task(user_data)
        user_data['completed_tasks'] = user_data.get('completed_tasks', 0) + 1
        message_suffix = "\n\n💫 <b>Отложенное задание выполнено! Молодец!</b>"
    
    rank_updated = await utils.update_user_rank(user_data)
    
    await utils.save_user(user_id, user_data)
    
    rank_message = ""
    if rank_updated:
        current_rank = user_data.get('rank', 'putnik')
        rank_info = await utils.get_rank_info(current_rank)
        rank_message = f"\n\n🏆 <b>Поздравляем! Новый ранг: {rank_info.get('name', '')}</b>"
    
    completed_tasks = user_data.get('completed_tasks', 0)
    
    await message.answer(
        f"🎉 <b>ОТЛИЧНАЯ РАБОТА!</b>\n\n"
        f"Еще один шаг к сильной версии себя!{message_suffix}"
        f"{rank_message}\n\n"
        f"<i>Сила воли, как мышца - растет с каждой тренировкой!</i>",
        reply_markup=keyboards.get_main_menu(user_id)
    )
    
    await utils.update_user_activity(user_id)

# В обработчике postpone_task_handler:

@dp.message(F.text == "⏭️ ОТЛОЖИТЬ")
async def postpone_task_handler(message: Message):
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    todays_tasks = await utils.get_todays_tasks(user_data)
    if not todays_tasks:
        await message.answer("❌ Нет активных заданий для откладывания!")
        return
    
    # Пытаемся отложить задание
    user_data, success = await utils.postpone_task(user_data)
    
    if success:
        await utils.save_user(user_id, user_data)
        
        motivation_messages = [
            "💫 Задание отложено! Вернешься к нему после 300-го дня!",
            "🔄 Отложил на потом! Сосредоточься на текущих задачах!",
            "⚡ Иногда лучше отложить, чем пропустить! Вернешься к нему позже!",
            "🎯 Задание сохранено! Оно вернётся после выполнения 300го дня",
        ]
        
        motivation = random.choice(motivation_messages)
        
        await message.answer(
            f"⏭️ <b>Задание отложено</b>\n\n"
            f"{motivation}",
            reply_markup=keyboards.get_main_menu(user_id)
        )
    else:
        # Достигнут лимит отложенных заданий
        await message.answer(
            f"❌ <b>Достигнут лимит отложенных заданий!</b>\n\n"
            f"Максимум можно отложить {config.MAX_POSTPONED_TASKS} заданий.\n"
            f"Выполни некоторые отложенные задания чтобы освободить место.\n\n"
            f"💡 <b>Совет:</b> Лучше выполнить задание сегодня, чем откладывать!",
            reply_markup=keyboards.get_main_menu(user_id)
        )
    
    await utils.update_user_activity(user_id)


# ОБНОВЛЯЕМ обработчик "Подписка 💎"
@dp.message(F.text == "Подписка 💎")
async def show_subscription(message: Message):
    """Показывает информацию о подписке"""
    try:
        user = message.from_user
        if not user:
            return
            
        user_id = user.id
        user_data = await get_user(user_id)
        
        if not user_data:
            await message.answer("Сначала зарегистрируйся через /start")
            return
        
        message_text = "<b>ПОДПИСКА 💎</b>\n\n"
        
        # Проверяем пробный период
        created_at = datetime.fromisoformat(user_data.get('created_at', datetime.now().isoformat()))
        days_passed = (datetime.now() - created_at).days
        is_trial = days_passed < 3
        
        if await is_subscription_active(user_data):
            try:
                sub_end = datetime.fromisoformat(user_data['subscription_end'])
                days_left = (sub_end - datetime.now()).days
                message_text += f"✅ <b>Статус:</b> Активна ({days_left} дней осталось)\n"
            except:
                message_text += "✅ <b>Статус:</b> Активна\n"
        elif is_trial:
            message_text += "✅ <b>Статус:</b> Активна\n"
            message_text += "Ты получаешь ежедневные задания!\n\n"
        else:
            message_text += "❌ <b>Статус:</b> Не активна\n"
            message_text += "Активируй подписку чтобы продолжить получать задания!\n\n"
        
        message_text += "<b>Доступные тарифы:</b>\n"
        
        for tariff_id, tariff in config.TARIFFS.items():
            if tariff_id in ['month', 'year', 'pair_year']:
                message_text += f"• {tariff['name']} - {tariff['price']} руб.\n"
        
        await message.answer(message_text, reply_markup=keyboards.get_payment_keyboard())
        
    except Exception as e:
        logger.error(f"❌ Ошибка в show_subscription: {e}")
        await message.answer("❌ Произошла ошибка при загрузке информации о подписке")

# НОВЫЙ обработчик "Инвайт-коды 💌"
@dp.message(F.text == "Инвайт-коды 💌")
async def show_invite_codes(message: Message):
    """Показывает раздел инвайт-кодов"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    message_text = (
        "<b>ИНВАЙТ-КОДЫ 💌</b>\n\n"
        "🎫 <b>Активировать инвайт-код</b> - если у тебя есть код активации\n\n"
        "🎁 <b>Подарить подписку другу</b> - купить доступ в подарок\n\n"
        "Выбери действие:"
    )
    
    await message.answer(message_text, reply_markup=keyboards.get_invite_codes_keyboard())

# НОВЫЙ обработчик "Мой легион ⚔️"
# ЗАМЕНЯЕМ старый обработчик на новый:
@dp.message(F.text == "Мой легион ⚔️")
async def show_my_legion(message: Message):
    """Показывает реферальную систему сразу при входе в Мой легион"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    referrals = user_data.get('referrals', [])
    earnings = user_data.get('referral_earnings', 0)
    ref_level_id, ref_level = await get_referral_level(len(referrals))
    
    bot_username = (await bot.get_me()).username
    if bot_username:
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
    else:
        referral_link = "Недоступно"
    
    message_text = (
        f"<b>МОЙ ЛЕГИОН ⚔️</b>\n\n"
        f"💫 <b>Приглашай друзей и получай до 50% от их платежей!</b>\n\n"
        f"• Приглашено друзей: {len(referrals)}\n"
        f"• Заработано: {earnings} руб.\n"
        f"• Текущий уровень: {ref_level['name']}\n"
        f"• Ваш процент: {ref_level['percent']}%\n\n"
        f"📤 <b>Просто нажми кнопку ниже чтобы отправить приглашение!</b>\n"
        f"Выбери друга из списка контактов - мы отправим красивое сообщение с объяснением системы."
    )
    
    await message.answer(message_text, reply_markup=keyboards.get_my_referral_keyboard())
@dp.message(F.text == "Реферальная программа 🤝")
async def show_referral(message: Message):
    """Показывает реферальную программу с кнопкой отправки приглашения"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await get_user(user_id)
    
    if not user_data:
        return
    
    referrals = user_data.get('referrals', [])
    earnings = user_data.get('referral_earnings', 0)
    ref_level_id, ref_level = await get_referral_level(len(referrals))
    
    bot_username = (await bot.get_me()).username
    if bot_username:
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
    else:
        referral_link = "Недоступно"
    
    message_text = (
        f"<b>РЕФЕРАЛЬНАЯ ПРОГРАММА 🤝</b>\n\n"
        f"💫 <b>Приглашай друзей и получай до 50% от их платежей!</b>\n\n"
        f"• Приглашено друзей: {len(referrals)}\n"
        f"• Заработано: {earnings} руб.\n"
        f"• Текущий уровень: {ref_level['name']}\n"
        f"• Ваш процент: {ref_level['percent']}%\n\n"
        f"📤 <b>Просто нажми кнопку ниже чтобы отправить приглашение!</b>\n"
        f"Выбери друга из списка контактов - мы отправим красивое сообщение с объяснением системы."
    )
    
    await message.answer(message_text, reply_markup=get_my_referral_keyboard())
    await update_user_activity(user_id)

@dp.message(Command("ref"))
async def cmd_ref(message: Message):
    """Команда для получения реферальной ссылки с кнопкой отправки"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    referrals = user_data.get('referrals', [])
    earnings = user_data.get('referral_earnings', 0)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    await message.answer(
        f"🔗 <b>ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА</b>\n\n"
        f"Приглашено: {len(referrals)} чел. | Заработано: {earnings} руб.\n\n"
        f"📤 <b>Просто нажми кнопку ниже чтобы отправить приглашение другу!</b>\n"
        f"Выбери контакт из списка - мы отправим красивое сообщение с объяснением системы.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="📤 Отправить приглашение", 
                    switch_inline_query="invite"
                )
            ]]
        )
    )
    await update_user_activity(user_id)
@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery):
    """Возврат в главное меню из любого раздела"""
    try:
        user = callback.from_user
        if not user:
            await callback.answer("❌ Ошибка пользователя")
            return
            
        if not callback.message:
            await callback.answer("❌ Ошибка сообщения")
            return
            
        # Пытаемся удалить сообщение с инлайн-клавиатурой
        try:
            await callback.message.delete()
        except:
            pass  # Если не удалось удалить - продолжаем
        
        # Отправляем главное меню
        await callback.message.answer(
            "Главное меню:",
            reply_markup=keyboards.get_main_menu(user.id)
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в back_to_main: {e}")
        try:
            await callback.answer("❌ Ошибка возврата в меню")
        except:
            pass
    
    try:
        await callback.answer()
    except:
        pass
# CALLBACK ОБРАБОТЧИКИ
@dp.callback_query(F.data == "get_referral_link")
async def get_referral_link(callback: CallbackQuery):
    """Генерирует реферальную ссылку"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    user_id = user.id
    bot_username = (await bot.get_me()).username
    if bot_username:
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
    else:
        referral_link = "Недоступно"
    
    try:
        await callback.message.edit_text( 
            f"<b>🔗 ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА</b>\n\n"
            f"<code>{referral_link}</code>\n\n"
            f"Отправляй эту ссылку друзьям!"
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()


@dp.message(Command("debug_payments"))
async def debug_payments_command(message: Message):
    """Отладочная информация о платежной системе"""
    user = message.from_user
    if not user:
        return
        
    debug_info = (
        f"🔧 <b>ОТЛАДКА ПЛАТЕЖНОЙ СИСТЕМЫ</b>\n\n"
        f"🤖 <b>Настройки бота:</b>\n"
        f"• Username: @{(await bot.get_me()).username}\n\n"
        f"💳 <b>ЮKassa настройки:</b>\n"
        f"• Shop ID: {config.YOOKASSA_SHOP_ID[:10]}...\n"
        f"• Secret Key: {config.YOOKASSA_SECRET_KEY[:10]}...\n"
        f"• Return URL: {config.YOOKASSA_RETURN_URL}\n\n"
        f"💰 <b>Тарифы:</b>\n"
    )
    
    for tariff_id, tariff in config.TARIFFS.items():
        debug_info += f"• {tariff['name']}: {tariff['price']} руб. ({tariff['days']} дней)\n"
    
    await message.answer(debug_info)

@dp.message(Command("check_payments"))
async def check_payments_command(message: Message):
    """Проверка созданных платежей"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    payments = await utils.read_json(config.PAYMENTS_FILE)
    
    if not payments:
        await message.answer("❌ В базе нет платежей")
        return
    
    message_text = f"📊 <b>Платежи в базе:</b> {len(payments)}\n\n"
    
    for i, (payment_id, payment_data) in enumerate(list(payments.items())[:5]):
        status = payment_data.get('status', 'unknown')
        amount = payment_data.get('amount', 0)
        user_id = payment_data.get('user_id', 'unknown')
        tariff_id = payment_data.get('tariff_id', 'unknown')
        
        message_text += (
            f"{i+1}. ID: {payment_id[:8]}...\n"
            f"   💰 {amount} руб. | 👤 {user_id}\n"
            f"   📦 {tariff_id} | 📊 {status}\n\n"
        )
    
    if len(payments) > 5:
        message_text += f"... и еще {len(payments) - 5} платежей"
    
    await message.answer(message_text)
@dp.callback_query(F.data.startswith("tariff_"))
async def process_tariff_selection(callback: CallbackQuery):
    """Обработка выбора тарифа с улучшенной обработкой ошибок"""
    if not callback.data:
        await callback.answer("❌ Ошибка: данные не найдены")
        return
        
    tariff_id = callback.data.replace("tariff_", "")
    tariff = config.TARIFFS.get(tariff_id)
    
    if not tariff:
        await callback.answer("❌ Тариф не найден")
        return
    
    if not callback.message:
        await callback.answer("❌ Ошибка: сообщение не найдено")
        return
    
    user = callback.from_user
    user_id = user.id
    
    try:
        # Создаем платеж в ЮKassa
        description = f"{tariff['name']} для пользователя {user.first_name or user.id}"
        payment_data = await payments.create_yookassa_payment(
            amount=tariff['price'],
            description=description,
            user_id=user_id,
            tariff_id=tariff_id
        )
        
        if not payment_data:
            await callback.answer("❌ Ошибка создания платежа. Попробуйте позже.")
            return
        
        # Формируем сообщение об оплате
        message_text = (
            f"<b>💎 ОПЛАТА ПОДПИСКИ</b>\n\n"
            f"📦 <b>Тариф:</b> {tariff['name']}\n"
            f"💰 <b>Сумма:</b> {tariff['price']} руб.\n"
            f"⏰ <b>Срок:</b> {tariff['days']} дней\n\n"
        )
        
        # Для парных тарифов добавляем пояснение
        if tariff_id == "pair_year":
            message_text += (
                "👥 <b>Это парная подписка на двух человек!</b>\n\n"
                "После успешной оплаты:\n"
                "• Ваша подписка активируется автоматически\n"
                "• Вы получите инвайт-код для второго участника\n"
                "• Передайте код другу для активации\n\n"
            )
        
        message_text += (
            f"🔗 <b>Ссылка для оплаты:</b>\n"
            f"<a href='{payment_data['confirmation_url']}'>Нажмите для перехода к оплате</a>\n\n"
            
            f"📱 <b>После оплаты:</b>\n"
            f"1. Вернитесь в бота\n"
            f"2. Нажмите кнопку «✅ Проверить оплату» ниже\n"
            f"3. Подписка активируется автоматически\n\n"
            
            f"⏳ <b>Платеж действителен 30 минут</b>\n"
            f"💡 <b>ID платежа:</b> <code>{payment_data['payment_id'][:8]}...</code>"
        )
        
        # Клавиатура с кнопками
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔗 Перейти к оплате", 
                    url=payment_data['confirmation_url']
                )],
                [InlineKeyboardButton(
                    text="✅ Проверить оплату", 
                    callback_data=f"check_payment_{payment_data['payment_id']}"
                )],
                [InlineKeyboardButton(
                    text="🔄 Обновить страницу оплаты", 
                    callback_data=f"refresh_payment_{payment_data['payment_id']}"
                )],
                [InlineKeyboardButton(
                    text="🔙 Назад к тарифам", 
                    callback_data="back_to_tariffs"
                )]
            ]
        )
        
        try:
            await callback.message.edit_text(message_text, reply_markup=keyboard)
            await callback.answer("✅ Платеж создан! Перейдите по ссылке для оплаты.")
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.answer("❌ Не удалось обновить сообщение")
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания платежа: {e}")
        await callback.answer("❌ Ошибка при создании платежа")
@dp.callback_query(F.data.startswith("check_payment_"))
async def check_payment_handler(callback: CallbackQuery):
    """Проверка статуса оплаты с безопасной обработкой"""
    # ПРОВЕРКА ВСЕХ ВОЗМОЖНЫХ None
    if not callback or not callback.data:
        try:
            await callback.answer("❌ Ошибка данных")
        except:
            pass
        return
    
    payment_id = callback.data.replace("check_payment_", "") if callback.data else ""
    
    if not callback.from_user:
        try:
            await callback.answer("❌ Ошибка пользователя")
        except:
            pass
        return
    
    user = callback.from_user
    
    try:
        await callback.answer("🔄 Проверяем статус платежа...")
        
        # Проверяем статус платежа
        payment_status = await payments.check_payment_status(payment_id)
        payment_data = await payments.get_payment_data(payment_id)
        
        if not payment_data:
            await safe_edit_message(callback, "❌ Платеж не найден в базе данных")
            return
        
        if payment_data['user_id'] != user.id:
            await safe_edit_message(callback, "❌ Это не ваш платеж")
            return
        
        if payment_status == "succeeded":
            await activate_subscription_after_payment(payment_data, callback)
            
        elif payment_status == "pending":
            check_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔄 Проверить еще раз", 
                    callback_data=f"check_payment_{payment_id}"
                )
            ]])
            
            await safe_edit_message(
                callback,
                "⏳ <b>Платеж еще обрабатывается</b>\n\n"
                "Обычно это занимает несколько минут.\n"
                "Попробуйте проверить статус через 2-3 минуты.",
                check_keyboard
            )
            
        elif payment_status == "canceled":
            await safe_edit_message(
                callback,
                "❌ <b>Платеж отменен</b>\n\n"
                "Вы можете создать новый платеж или выбрать другой тариф.",
                keyboards.get_payment_keyboard()
            )
            
        elif payment_status is None:
            check_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔄 Попробовать снова", 
                    callback_data=f"check_payment_{payment_id}"
                )
            ]])
            
            await safe_edit_message(
                callback,
                "❌ <b>Не удалось проверить статус платежа</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку.",
                check_keyboard
            )
        else:
            check_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔄 Проверить статус", 
                    callback_data=f"check_payment_{payment_id}"
                )
            ]])
            
            await safe_edit_message(
                callback,
                f"📊 <b>Статус платежа:</b> {payment_status}\n\n"
                "Продолжайте ожидание или попробуйте проверить позже.",
                check_keyboard
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки платежа: {e}")
        await safe_edit_message(
            callback,
            "❌ <b>Произошла ошибка при проверке платежа</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку."
        )
@dp.callback_query(F.data.startswith("refresh_payment_"))
async def refresh_payment_handler(callback: CallbackQuery):
    """Обновление страницы оплаты"""
    if not callback or not callback.data:
        try:
            await callback.answer("❌ Ошибка данных")
        except:
            pass
        return
        
    if not callback.message:
        try:
            await callback.answer("❌ Ошибка: сообщение не найдено")
        except:
            pass
        return
        
    payment_id = callback.data.replace("refresh_payment_", "") if callback.data else ""
    payment_data = await payments.get_payment_data(payment_id)
    
    if payment_data:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔗 Перейти к оплате", 
                url=payment_data['confirmation_url']
            )],
            [InlineKeyboardButton(
                text="✅ Проверить оплату", 
                callback_data=f"check_payment_{payment_data['payment_id']}"
            )]
        ])
        
        success = await safe_edit_reply_markup(callback, keyboard)
        if success:
            await callback.answer("✅ Ссылка обновлена")
        else:
            await callback.answer("❌ Ошибка обновления")
    else:
        await callback.answer("❌ Платеж не найден")

@dp.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs_handler(callback: CallbackQuery):
    """Возврат к выбору тарифов"""
    if not callback:
        return
        
    if not callback.message:
        try:
            await callback.answer("❌ Ошибка: сообщение не найдено")
        except:
            pass
        return
        
    try:
        success = await safe_edit_message(
            callback,
            "<b>💎 ВЫБОР ПОДПИСКИ</b>\n\n"
            "Выберите подходящий тариф:",
            keyboards.get_payment_keyboard()
        )
        if success:
            await callback.answer()
        else:
            await callback.answer("❌ Ошибка обновления")
    except Exception as e:
        logger.error(f"Ошибка возврата к тарифам: {e}")
        await callback.answer("❌ Ошибка")

async def activate_subscription_after_payment(payment_data, callback):
    """Активация подписки после успешной оплаты"""
    if not callback:
        return
        
    user_id = payment_data['user_id']
    tariff_id = payment_data['tariff_id']
    tariff = config.TARIFFS.get(tariff_id)
    
    if not tariff:
        await callback.answer("❌ Ошибка: тариф не найден")
        return
    
    user_data = await utils.get_user(user_id)
    if not user_data:
        await callback.answer("❌ Ошибка: пользователь не найден")
        return
    
    # Обновляем статус платежа
    await payments.update_payment_status(payment_data['payment_id'], 'succeeded')
    
    if tariff_id == "pair_year":
        await activate_pair_subscription(user_data, user_id, tariff, callback)
    else:
        updated_user_data = await utils.add_subscription_days(user_data, tariff['days'])
        await utils.save_user(user_id, updated_user_data)
        
        success_message = (
            f"✅ <b>Подписка активирована!</b>\n\n"
            f"💎 Тариф: {tariff['name']}\n"
            f"⏰ Срок: {tariff['days']} дней\n"
            f"🎯 Теперь у вас есть доступ ко всем заданиям!\n\n"
            f"Задания будут приходить ежедневно в 9:00 🕘"
        )
        
        success = await safe_edit_message(callback, success_message)
        if not success:
            await safe_send_message(callback, success_message)

async def activate_pair_subscription(user_data, user_id, tariff, callback):
    """Активация парной подписки"""
    if not callback:
        return
        
    try:
        updated_user_data = await utils.add_subscription_days(user_data, tariff['days'])
        
        # Создаем инвайт-код для второго участника
        invite_code = await utils.create_invite_code(
            code_type="pair_year_second",
            days=tariff['days'],
            max_uses=1,
            created_by=user_id,
            pair_owner=user_id
        )
        
        await utils.save_user(user_id, updated_user_data)
        
        success_message = (
            f"✅ <b>Парная подписка активирована!</b>\n\n"
            f"💎 <b>Ваша подписка:</b>\n"
            f"• Активна на {tariff['days']} дней\n"
            f"• Доступ ко всем заданиям\n\n"
            f"🎫 <b>Инвайт-код для второго участника:</b>\n"
            f"<code>{invite_code}</code>\n\n"
            f"<b>Как передать код:</b>\n"
            f"1. Отправьте этот код другу\n"
            f"2. Он должен зайти в раздел «Инвайт-коды 💌»\n"
            f"3. Нажать «🎫 Активировать инвайт-код»\n"
            f"4. Ввести код и активировать подписку\n\n"
            f"⚠️ <b>Внимание:</b> Код можно использовать только 1 раз!\n"
            f"⏰ Действителен 30 дней"
        )
        
        success = await safe_edit_message(callback, success_message)
        if not success:
            await safe_send_message(callback, success_message)
        
        # Уведомляем админа
        try:
            user = callback.from_user
            if user:
                admin_message = (
                    f"🎉 <b>Новая парная подписка через ЮKassa!</b>\n\n"
                    f"👤 Пользователь: {user.first_name} (@{user.username or 'нет'})\n"
                    f"🆔 ID: {user_id}\n"
                    f"💎 Тариф: {tariff['name']}\n"
                    f"💰 Сумма: {tariff['price']} руб.\n"
                    f"🎫 Инвайт-код: {invite_code}"
                )
                await bot.send_message(config.ADMIN_ID, admin_message)
        except Exception as e:
            logger.error(f"Ошибка уведомления админа: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка активации парной подписки: {e}")
        error_message = "❌ Произошла ошибка при активации подписки. Обратитесь в поддержку."
        await safe_edit_message(callback, error_message)

@dp.message(Command("refstats"))
async def cmd_refstats(message: Message):
    """Команда для просмотра реферальной статистики"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    referrals = user_data.get('referrals', [])
    earnings = user_data.get('referral_earnings', 0)
    ref_level_id, ref_level = await utils.get_referral_level(len(referrals))
    
    # Подсчитываем активных рефералов
    active_refs = 0
    for ref_id in referrals:
        ref_data = await utils.get_user(ref_id)
        if ref_data and (await utils.is_subscription_active(ref_data) or await utils.is_in_trial_period(ref_data)):
            active_refs += 1
    
    message_text = (
        f"📊 <b>Реферальная статистика</b>\n\n"
        f"• Всего приглашено: {len(referrals)} чел.\n"
        f"• Активных: {active_refs} чел.\n"
        f"• Неактивных: {len(referrals) - active_refs} чел.\n"
        f"• Заработано: {earnings} руб.\n"
        f"• Текущий уровень: {ref_level['name']}\n"
        f"• Ваш процент: {ref_level['percent']}%\n\n"
    )
    
    if len(referrals) > 0:
        message_text += "<b>Последние 5 рефералов:</b>\n"
        for i, ref_id in enumerate(referrals[:5], 1):
            ref_data = await utils.get_user(ref_id)
            if ref_data:
                name = ref_data.get('first_name', 'Пользователь')
                status = "🟢" if (await utils.is_subscription_active(ref_data) or await utils.is_in_trial_period(ref_data)) else "🔴"
                message_text += f"{i}. {status} {name}\n"
    
    await message.answer(message_text)
    await utils.update_user_activity(user_id)
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    try:
        await callback.message.delete() # pyright: ignore[reportAttributeAccessIssue]
        await callback.message.answer(
            "Главное меню:",
            reply_markup=get_main_menu(user.id)
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке возврата в главное меню: {e}")
        await callback.answer("Не удалось выполнить действие")
    
    await callback.answer()

# Добавить в bot.py после существующих обработчиков:
@dp.message(F.text == "🔙 Назад")
async def back_to_main_from_task(message: Message):
    """Возврат в главное меню из задания"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    await message.answer(
        "Главное меню:",
        reply_markup=keyboards.get_main_menu(user_id)
    )
    await utils.update_user_activity(user_id)

@dp.callback_query(F.data == "back_to_main_from_task")
async def back_to_main_from_task_callback(callback: CallbackQuery):
    """Возврат в главное меню из inline клавиатуры"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    try:
        await callback.message.delete()
        await callback.message.answer(
            "Главное меню:",
            reply_markup=keyboards.get_main_menu(user.id)
        )
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")
        await callback.answer("Не удалось вернуться в меню")
    
    await callback.answer()
# ========== АДМИН ПАНЕЛЬ ==========

@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    """Показывает админ-панель"""
    user = message.from_user
    if not user:
        return
        
    if user.id != config.ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к админ-панели")
        return
    
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=admin_keyboard
    )

@dp.message(F.text == "🔙 Главное меню")
async def back_to_main_from_admin(message: Message):
    """Возврат в главное меню из админки"""
    user = message.from_user
    if not user:
        return
        
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu(user.id)
    )

@dp.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    """Статистика для админа"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    from keyboards import get_admin_stats_keyboard
    
    # Получаем базовую статистику
    users = await get_all_users()
    total_users = len(users)
    
    # Исправляем ошибку с sum() - используем ручной подсчет
    active_users_count = 0
    for user_data in users.values():
        if await is_subscription_active(user_data) or await is_in_trial_period(user_data):
            active_users_count += 1
    
    stats_text = (
        f"📊 <b>Общая статистика</b>\n\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Активных подписок: {active_users_count}\n"
        f"• Неактивных: {total_users - active_users_count}\n\n"
        f"Выберите раздел для детальной статистики:"
    )
    
    await message.answer(stats_text, reply_markup=get_admin_stats_keyboard())

@dp.message(F.text == "👥 Пользователи")
async def admin_users(message: Message):
    """Управление пользователями"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    from keyboards import get_admin_users_keyboard
    
    users_text = (
        "👥 <b>Управление пользователями</b>\n\n"
        "Выберите действие для работы с пользователями:"
    )
    
    await message.answer(users_text, reply_markup=get_admin_users_keyboard())

@dp.message(F.text == "📢 Рассылка")
async def admin_broadcast(message: Message):
    """Рассылка сообщений"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    await message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Для создания рассылки отправьте сообщение в формате:\n"
        "<code>РАССЫЛКА|заголовок|текст сообщения</code>\n\n"
        "Пример:\n"
        "<code>РАССЫЛКА|Важное обновление|Дорогие пользователи, появились новые функции!</code>"
    )

@dp.message(F.text == "💳 Платежи")
async def admin_payments(message: Message):
    """Управление платежами"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    await message.answer(
        "💳 <b>Управление платежами</b>\n\n"
        "Раздел в разработке...\n"
        "Здесь будут отображаться платежи и финансовые отчеты."
    )

@dp.message(F.text == "🎫 Инвайт-коды")
async def admin_invites(message: Message):
    """Управление инвайт-кодами"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    from keyboards import get_admin_invite_keyboard
    
    invites_text = (
        "🎫 <b>Управление инвайт-кодами</b>\n\n"
        "Создавайте и управляйте пригласительными кодами:"
    )
    
    await message.answer(invites_text, reply_markup=get_admin_invite_keyboard())

@dp.message(F.text == "➕ Добавить задание")
async def admin_add_task(message: Message):
    """Добавление нового задания"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
        
    await message.answer(
        "➕ <b>Добавление задания</b>\n\n"
        "Для добавления задания отправьте сообщение в формате:\n"
        "<code>ЗАДАНИЕ|день|архетип|текст задания</code>\n\n"
        "Пример:\n"
        "<code>ЗАДАНИЕ|1|spartan|Сделайте 20 отжиманий</code>\n"
        "<code>ЗАДАНИЕ|1|amazon|Сделайте 15 приседаний</code>"
    )

# Обработчики для инлайн кнопок админки
@dp.callback_query(F.data == "admin_back")
async def admin_back_handler(callback: CallbackQuery):
    """Возврат в главное меню админки"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    # Используем answer вместо edit_text для ReplyKeyboardMarkup
    await callback.message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=admin_keyboard
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_stats_general")
async def admin_stats_general(callback: CallbackQuery):
    """Детальная общая статистика"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    users = await get_all_users()
    total_users = len(users)
    
    # Подсчет статистики
    active_subs = 0
    trial_users = 0
    spartans = 0
    amazons = 0
    total_days = 0
    
    for user_data in users.values():
        if await is_subscription_active(user_data):
            active_subs += 1
        if await is_in_trial_period(user_data):
            trial_users += 1
        if user_data.get('archetype') == 'spartan':
            spartans += 1
        elif user_data.get('archetype') == 'amazon':
            amazons += 1
        total_days += user_data.get('current_day', 0)
    
    avg_day = total_days // max(1, total_users)
    
    stats_text = (
        f"📈 <b>Детальная статистика</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Спартанцы: {spartans}\n"
        f"• Амазонки: {amazons}\n\n"
        f"💎 <b>Подписки:</b>\n"
        f"• Активные: {active_subs}\n"
        f"• Пробные: {trial_users}\n"
        f"• Неактивные: {total_users - active_subs - trial_users}\n\n"
        f"📊 <b>Прогресс:</b>\n"
        f"• Средний день: {avg_day}"
    )
    
    from keyboards import get_admin_stats_keyboard
    
    # Используем answer вместо edit_text чтобы избежать ошибок
    await callback.message.answer(stats_text, reply_markup=get_admin_stats_keyboard())
    await callback.answer()

# Добавить обработчики для остальных админских callback'ов
@dp.callback_query(F.data == "admin_stats_active")
async def admin_stats_active(callback: CallbackQuery):
    """Статистика активных пользователей"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    users = await get_all_users()
    active_users = []
    
    for user_id, user_data in users.items():
        if await is_subscription_active(user_data) or await is_in_trial_period(user_data):
            active_users.append((user_id, user_data))
    
    stats_text = (
        f"👥 <b>Активные пользователи</b>\n\n"
        f"• Всего активных: {len(active_users)}\n\n"
        f"<b>Последние 10 активных:</b>\n"
    )
    
    for i, (user_id, user_data) in enumerate(active_users[:10], 1):
        username = user_data.get('username', 'нет username')
        first_name = user_data.get('first_name', 'Неизвестно')
        stats_text += f"{i}. {first_name} (@{username}) - день {user_data.get('current_day', 0)}\n"
    
    from keyboards import get_admin_stats_keyboard
    await callback.message.answer(stats_text, reply_markup=get_admin_stats_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_stats_subscriptions")
async def admin_stats_subscriptions(callback: CallbackQuery):
    """Статистика подписок"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    users = await get_all_users()
    
    active_count = 0
    trial_count = 0
    inactive_count = 0
    
    for user_data in users.values():
        if await is_subscription_active(user_data):
            active_count += 1
        elif await is_in_trial_period(user_data):
            trial_count += 1
        else:
            inactive_count += 1
    
    stats_text = (
        f"💎 <b>Статистика подписок</b>\n\n"
        f"• Активные подписки: {active_count}\n"
        f"• Пробные периоды: {trial_count}\n"
        f"• Неактивные: {inactive_count}\n"
        f"• Всего: {len(users)}\n\n"
        f"<b>Процентное соотношение:</b>\n"
        f"• Активные: {active_count/len(users)*100:.1f}%\n"
        f"• Пробные: {trial_count/len(users)*100:.1f}%\n"
        f"• Неактивные: {inactive_count/len(users)*100:.1f}%"
    )
    
    from keyboards import get_admin_stats_keyboard
    await callback.message.answer(stats_text, reply_markup=get_admin_stats_keyboard())
    await callback.answer()
    """Детальная общая статистика"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    users = await get_all_users()
    total_users = len(users)
    
    # Подсчет статистики
    active_subs = 0
    trial_users = 0
    spartans = 0
    amazons = 0
    total_days = 0
    
    for user_data in users.values():
        if await is_subscription_active(user_data):
            active_subs += 1
        if await is_in_trial_period(user_data):
            trial_users += 1
        if user_data.get('archetype') == 'spartan':
            spartans += 1
        elif user_data.get('archetype') == 'amazon':
            amazons += 1
        total_days += user_data.get('current_day', 0)
    
    avg_day = total_days // max(1, total_users)
    
    stats_text = (
        f"📈 <b>Детальная статистика</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Спартанцы: {spartans}\n"
        f"• Амазонки: {amazons}\n\n"
        f"💎 <b>Подписки:</b>\n"
        f"• Активные: {active_subs}\n"
        f"• Пробные: {trial_users}\n"
        f"• Неактивные: {total_users - active_subs - trial_users}\n\n"
        f"📊 <b>Прогресс:</b>\n"
        f"• Средний день: {avg_day}"
    )
    
    from keyboards import get_admin_stats_keyboard
    try:
        await callback.message.edit_text(stats_text, reply_markup=get_admin_stats_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.message.answer(stats_text, reply_markup=get_admin_stats_keyboard())
    
    await callback.answer()
    """Детальная общая статистика"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    users = await get_all_users()
    total_users = len(users)
    
    # Подсчет статистики
    active_subs = 0
    trial_users = 0
    spartans = 0
    amazons = 0
    
    for user_data in users.values():
        if await is_subscription_active(user_data):
            active_subs += 1
        if await is_in_trial_period(user_data):
            trial_users += 1
        if user_data.get('archetype') == 'spartan':
            spartans += 1
        elif user_data.get('archetype') == 'amazon':
            amazons += 1
    
    stats_text = (
        f"📈 <b>Детальная статистика</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Спартанцы: {spartans}\n"
        f"• Амазонки: {amazons}\n\n"
        f"💎 <b>Подписки:</b>\n"
        f"• Активные: {active_subs}\n"
        f"• Пробные: {trial_users}\n"
        f"• Неактивные: {total_users - active_subs - trial_users}\n\n"
        f"📊 <b>Прогресс:</b>\n"
        f"• Средний день: {sum(u.get('current_day', 0) for u in users.values()) // max(1, total_users)}"
    )
    
    from keyboards import get_admin_stats_keyboard
    await callback.message.edit_text(stats_text, reply_markup=get_admin_stats_keyboard())
    await callback.answer()

# ========== ОБРАБОТЧИКИ ИНВАЙТ-КОДОВ ==========

@dp.callback_query(F.data == "invite_create")
async def invite_create_handler(callback: CallbackQuery):
    """Создание инвайт-кода"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    await callback.message.edit_text(
        "🎫 <b>Создание инвайт-кода</b>\n\n"
        "Выберите тип подписки для инвайт-кода:",
        reply_markup=get_invite_code_types_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("invite_type_"))
async def invite_type_selected(callback: CallbackQuery):
    """Обработка выбора типа инвайт-кода"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    if not callback.data:
        await callback.answer("Ошибка данных")
        return
        
    code_type = callback.data.replace("invite_type_", "")
    
    # Создаем инвайт-код
    invite_code = await utils.create_invite_code(
        code_type=code_type,
        created_by=user.id
    )
    
    code_info = config.INVITE_CODE_TYPES.get(code_type, {})
    days = code_info.get('days', 0)
    name = code_info.get('name', 'Подписка')
    
    if code_type == "detox_sprint":
        message_text = (
            f"✅ <b>Инвайт-код для спринта создан!</b>\n\n"
            f"<b>Тип:</b> {name}\n"
            f"<b>Длительность:</b> 4 дня спринта\n"
            f"<b>Код:</b> <code>{invite_code}</code>\n\n"
            f"Пользователь получит доступ к 4-дневному спринту цифрового детокса.\n"
            f"После завершения сможет продолжить за 1 рубль."
        )
    else:
        message_text = (
            f"✅ <b>Инвайт-код создан!</b>\n\n"
            f"<b>Тип:</b> {name}\n"
            f"<b>Дней:</b> {days}\n"
            f"<b>Код:</b> <code>{invite_code}</code>\n\n"
            f"Пользователь может активировать его через меню:\n"
            f"<b>🎫 Активировать инвайт</b>"
        )
    
    await callback.message.edit_text(message_text)
    await callback.answer()
    """Обработка выбора типа инвайт-кода"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    if not callback.data:
        await callback.answer("Ошибка данных")
        return
        
    code_type = callback.data.replace("invite_type_", "")
    
    # Создаем инвайт-код
    invite_code = await utils.create_invite_code(
        code_type=code_type,
        created_by=user.id
    )
    
    code_info = config.INVITE_CODE_TYPES.get(code_type, {})
    days = code_info.get('days', 0)
    name = code_info.get('name', 'Подписка')
    
    if code_type == "detox_sprint":
        message_text = (
            f"✅ <b>Инвайт-код для спринта создан!</b>\n\n"
            f"<b>Тип:</b> {name}\n"
            f"<b>Длительность:</b> 4 дня спринта\n"
            f"<b>Код:</b> <code>{invite_code}</code>\n\n"
            f"Пользователь получит доступ к 4-дневному спринту цифрового детокса.\n"
            f"После завершения сможет продолжить за 1 рубль."
        )
    else:
        message_text = (
            f"✅ <b>Инвайт-код создан!</b>\n\n"
            f"<b>Тип:</b> {name}\n"
            f"<b>Дней:</b> {days}\n"
            f"<b>Код:</b> <code>{invite_code}</code>\n\n"
            f"Пользователь может активировать его через меню:\n"
            f"<b>🎫 Активировать инвайт</b>"
        )
    
    await callback.message.edit_text(message_text)
    await callback.answer()
    """Обработка выбора типа инвайт-кода"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    if not callback.data:
        await callback.answer("Ошибка данных")
        return
        
    code_type = callback.data.replace("invite_type_", "")
    
    # Создаем инвайт-код
    invite_code = await utils.create_invite_code(
        code_type=code_type,
        created_by=user.id
    )
    
    code_info = config.INVITE_CODE_TYPES.get(code_type, {})
    days = code_info.get('days', 30)
    name = code_info.get('name', 'Подписка')
    
    await callback.message.edit_text(
        f"✅ <b>Инвайт-код создан!</b>\n\n"
        f"<b>Тип:</b> {name}\n"
        f"<b>Дней:</b> {days}\n"
        f"<b>Код:</b> <code>{invite_code}</code>\n\n"
        f"Пользователь может активировать его через меню:\n"
        f"<b>🎫 Активировать инвайт</b>"
    )
    await callback.answer()

@dp.callback_query(F.data == "invite_list")
async def invite_list_handler(callback: CallbackQuery):
    """Список активных инвайт-кодов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    # ИСПОЛЬЗУЕМ ФИЛЬТРОВАННУЮ ВЕРСИЮ БЕЗ СКРЫТЫХ КОДОВ
    invite_codes = await utils.get_all_invite_codes(include_hidden=False)
    
    if not invite_codes:
        await callback.message.edit_text(
            "📋 <b>Список инвайт-кодов</b>\n\n"
            "Активных кодов нет.",
            reply_markup=keyboards.get_admin_invite_keyboard()
        )
        await callback.answer()
        return
    
    active_codes = []
    inactive_codes = []
    
    for code, data in invite_codes.items():
        if data.get('is_active', True) and not data.get('is_hidden', False):
            active_codes.append((code, data))
        else:
            inactive_codes.append((code, data))
    
    message_text = "📋 <b>Список инвайт-кодов</b>\n\n"
    
    if active_codes:
        message_text += "<b>🟢 Активные коды:</b>\n"
        for code, data in active_codes[:10]:
            uses = f"{data.get('used_count', 0)}/{data.get('max_uses', 1)}"
            message_text += f"• <code>{code}</code> - {data.get('name', 'Подписка')} (исп: {uses})\n"
    
    if inactive_codes:
        message_text += f"\n<b>🔴 Неактивные коды:</b> {len(inactive_codes)}"
    
    if len(active_codes) > 10:
        message_text += f"\n\n... и еще {len(active_codes) - 10} активных кодов"
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboards.get_admin_invite_keyboard()
    )
    await callback.answer()

@dp.message(F.text == "🎫 Активировать инвайт")
async def activate_invite_command(message: Message, state: FSMContext):
    """Активация инвайт-кода"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    await message.answer(
        "🎫 <b>Активация инвайт-кода</b>\n\n"
        "Введите инвайт-код для активации подписки:"
    )
    await state.set_state(UserStates.waiting_for_invite)

@dp.message(UserStates.waiting_for_invite)
async def process_invite_code(message: Message, state: FSMContext):
    """Обработка введенного инвайт-кода - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    user = message.from_user
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
        
    if not message.text:
        await message.answer("Пожалуйста, введите инвайт-код:")
        return
    
    invite_code = message.text.strip()
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        await state.clear()
        return
    
    # ОДНОКРАТНАЯ АКТИВАЦИЯ С ПРОВЕРКОЙ
    success, result = await utils.use_invite_code(invite_code, user_id)
    
    if success:
        invite_data = result
        
        if invite_data.get('type') == 'detox_sprint':
            # Запускаем спринт
            updated_user_data = await utils.start_detox_sprint(user_data)
            await utils.save_user(user_id, updated_user_data)
            
            # СРАЗУ ПОКАЗЫВАЕМ ПЕРВОЕ ЗАДАНИЕ
            sprint_day = 1
            task_text = await utils.get_sprint_task(sprint_day)
            
            await message.answer(
                "🎯 <b>Добро пожаловать в 4-дневный спринт ЦИФРОВОЙ ДЕТОКС!</b>\n\n"
                "Твой путь к цифровой свободе начинается!\n\n"
                "💪 <b>Первое задание уже ждет тебя ниже!</b>",
                reply_markup=keyboards.get_main_menu(user.id)
            )
            
            # ОТПРАВЛЯЕМ ЗАДАНИЕ СРАЗУ
            if task_text:
                task_message = (
                    f"⚡ <b>СПРИНТ: ДЕНЬ 1/4</b>\n\n"
                    f"<b>Задание дня #1</b>\n\n"
                    f"{task_text}\n\n"
                    f"💪 Твой шаг к цифровой свободе!\n"
                    f"⏰ До 23:59 на выполнение"
                )
                await message.answer(task_message, reply_markup=keyboards.task_keyboard)
                
        else:
            # Старая логика для обычных кодов
            days = invite_data.get('days', 30)
            updated_user_data = await utils.add_subscription_days(user_data, days)
            await utils.save_user(user_id, updated_user_data)
            
            await message.answer(
                f"✅ <b>Инвайт-код активирован!</b>\n\n"
                f"Вам добавлено <b>{days}</b> дней подписки.\n"
                f"Тип: {invite_data.get('name', 'Подписка')}\n\n"
                f"Теперь у вас есть доступ ко всем заданиям! 🎉",
                reply_markup=keyboards.get_main_menu(user.id)
            )
            
        # ОЧИЩАЕМ СОСТОЯНИЕ ПОСЛЕ УСПЕШНОЙ АКТИВАЦИИ
        await state.clear()
        
    else:
        error_message = result
        await message.answer(
            f"❌ <b>Не удалось активировать код</b>\n\n"
            f"{error_message}\n\n"
            f"Попробуйте другой код или обратитесь в поддержку: {config.SUPPORT_USERNAME}"
        )
        # НЕ очищаем состояние при ошибке - пользователь может попробовать другой код
    
    await utils.update_user_activity(user_id)


# ========== ОБРАБОТЧИКИ РЕФЕРАЛЬНОЙ ПРОГРАММЫ ==========

async def get_referral_link_with_text(user_id):
    """Генерирует реферальную ссылку с текстом для sharing"""
    bot_username = (await bot.get_me()).username
    if bot_username:
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        share_text = (
            f"🚀 Присоединяйся к челленджу «300 ПИНКОВ»!\n\n"
            f"Ежедневные задания для развития силы воли и дисциплины. "
            f"Выбери свой путь - 🛡️ Спартанец или ⚔️ Амазонка!\n\n"
            f"Переходи по ссылке: {referral_link}"
        )
        return referral_link, share_text
    return None, None

@dp.callback_query(F.data == "my_earnings")
async def my_earnings_handler(callback: CallbackQuery):
    """Показывает начисления по реферальной программе"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
        
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    referrals = user_data.get('referrals', [])
    earnings = user_data.get('referral_earnings', 0)
    ref_level_id, ref_level = await utils.get_referral_level(len(referrals))
    
    # Получаем информацию о платежах рефералов
    active_refs = 0
    paying_refs = 0
    
    for ref_id in referrals:
        ref_data = await utils.get_user(ref_id)
        if ref_data:
            if await utils.is_subscription_active(ref_data) or await utils.is_in_trial_period(ref_data):
                active_refs += 1
            # Считаем тех, кто уже оплатил (не в пробном периоде)
            if await utils.is_subscription_active(ref_data):
                paying_refs += 1
    
    bot_username = (await bot.get_me()).username
    if bot_username:
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
    else:
        referral_link = "Недоступно"
    
    message_text = (
        f"💰 <b>Мои начисления</b>\n\n"
        f"• Приглашено друзей: {len(referrals)} чел.\n"
        f"• Из них оплатили: {paying_refs} чел.\n"
        f"• Активных: {active_refs} чел.\n"
        f"• Заработано: {earnings} руб.\n"
        f"• Текущий уровень: {ref_level['name']}\n"
        f"• Ваш процент: {ref_level['percent']}%\n\n"
    )
    
    if len(referrals) == 0:
        message_text += (
            f"🎯 <b>Пригласи первого друга и стань Легионером!</b>\n"
            f"С первого же реферала ты будешь получать 30% от его платежей!\n\n"
        )
    else:
        message_text += "<b>Последние приглашенные:</b>\n"
        for i, ref_id in enumerate(referrals[:5], 1):
            ref_data = await utils.get_user(ref_id)
            if ref_data:
                name = ref_data.get('first_name', 'Пользователь')
                status = "💎" if await utils.is_subscription_active(ref_data) else "🆓" if await utils.is_in_trial_period(ref_data) else "❌"
                message_text += f"{i}. {status} {name}\n"
    
    if len(referrals) > 5:
        message_text += f"\n... и еще {len(referrals) - 5} пользователей"
    
    # Добавляем реферальную ссылку
    if referral_link:
        message_text += f"\n\n🔗 <b>Ваша реферальная ссылка:</b>\n<code>{referral_link}</code>"
    
    try:
        await callback.message.edit_text(
            message_text,
            reply_markup=get_my_referral_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()

@dp.callback_query(F.data == "full_referral_system")
async def full_referral_system_handler(callback: CallbackQuery):
    """Показывает полную реферальную систему"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
        
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    referrals_count = len(user_data.get('referrals', []))
    current_level_id, current_level = await utils.get_referral_level(referrals_count)
    bot_username = (await bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}" if bot_username else "Недоступно"
    
    message_text = (
        "🤝 <b>Полная реферальная система</b>\n\n"
        "Приглашай друзей и получай до 50% от их платежей, пока она в системе!\n\n"
        
        "<b>Уровни системы:</b>\n"
    )
    
    for level_id, level_info in config.REFERRAL_LEVELS.items():
        percent = level_info['percent']
        min_refs = level_info['min_refs']
        name = level_info['name']
        
        if level_id == current_level_id:
            message_text += f"• 🎯 <b>{name}</b> - {percent}% (твой уровень)\n"
        elif min_refs == 1:
            message_text += f"• 🚀 <b>{name}</b> - {percent}% (с 1 реферала)\n"
        elif min_refs > referrals_count:
            needed = min_refs - referrals_count
            message_text += f"• ⏳ <b>{name}</b> - {percent}% (нужно еще {needed})\n"
        else:
            message_text += f"• ✅ <b>{name}</b> - {percent}% (от {min_refs}+ рефералов)\n"
    
    message_text += (
        f"\n<b>Как это работает:</b>\n"
        f"1. Делись своей реферальной ссылкой\n"
        f"2. Друг оплачивает подписку - ты получаешь процент от суммы\n"
        f"3. <b>С первого же реферала - 30%!</b>\n\n"
              
        f"🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        
        f"📤 <b>Делись ссылкой с друзьями!</b>"
    )
    
    try:
        await callback.message.edit_text(
            message_text,
            reply_markup=get_my_referral_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()

@dp.callback_query(F.data == "whats_next_referral")
async def whats_next_referral_handler(callback: CallbackQuery):
    """Показывает, что ждет пользователя дальше в реферальной программе"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
        
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    referrals_count = len(user_data.get('referrals', []))
    current_level_id, current_level = await utils.get_referral_level(referrals_count)
    referral_link, share_text = await get_referral_link_with_text(user_id)
    
    message_text = (
        f"🚀 <b>Что меня ждёт дальше</b>\n\n"
        f"<b>Текущий статус:</b>\n"
        f"• Приглашено: {referrals_count} чел.\n"
        f"• Уровень: {current_level['name']}\n"
        f"• Процент: {current_level['percent']}%\n\n"
    )
    
    # Находим следующий уровень
    next_level = None
    for level_id, level_info in config.REFERRAL_LEVELS.items():
        if level_info['min_refs'] > referrals_count:
            next_level = level_info
            break
    
    if next_level:
        refs_needed = next_level['min_refs'] - referrals_count
        increase = next_level['percent'] - current_level['percent']
        
        message_text += (
            f"<b>Следующий уровень: {next_level['name']}</b>\n"
            f"• Процент: {next_level['percent']}% (+{increase}%)\n"
            f"• Нужно пригласить: еще {refs_needed} чел.\n\n"
        )
        
        # Показываем потенциальный заработок
        if referrals_count > 0:
            current_monthly = (referrals_count * 300 * current_level['percent']) / 100
            future_monthly = (referrals_count * 300 * next_level['percent']) / 100
            increase_monthly = future_monthly - current_monthly
            
            message_text += (
                f"<b>Потенциальный рост дохода:</b>\n"
                f"• Сейчас: ~{current_monthly:.0f} руб./мес\n"
                f"• Будет: ~{future_monthly:.0f} руб./мес\n"
                f"• Прирост: +{increase_monthly:.0f} руб./мес\n\n"
            )
        
        if refs_needed == 1:
            message_text += f"🎯 <b>Всего 1 человек до повышения уровня!</b>\n"
        elif refs_needed <= 3:
            message_text += f"🎯 <b>Всего {refs_needed} человека до повышения уровня!</b>\n"
    else:
        message_text += (
            f"🎉 <b>Поздравляем! Вы достигли максимального уровня - Император!</b>\n"
            f"Продолжайте приглашать друзей и увеличивайте свой доход!\n\n"
        )
    
    # Мотивационное сообщение для новичков
    if referrals_count == 0:
        message_text += (
            f"💫 <b>Начните прямо сейчас!</b>\n"
            f"Пригласите первого друга и сразу получите:\n"
            f"• Повышение до уровня <b>Легионер</b>\n"
            f"• 20% с каждого платежа вашего реферала\n"
            f"• ~60 руб. с каждой месячной подписки\n\n"
        )
    
    # Добавляем реферальную ссылку
    if referral_link:
        message_text += f"🔗 <b>Ваша реферальная ссылка:</b>\n<code>{referral_link}</code>"
    
    message_text += f"\n\n📤 <b>Делитесь ссылкой с друзьями!</b>"
    
    try:
        await callback.message.edit_text(
            message_text,
            reply_markup=get_my_referral_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()

@dp.callback_query(F.data == "get_referral_link")
async def get_referral_link_handler(callback: CallbackQuery):
    """Генерирует реферальную ссылку с полной информацией"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    referrals_count = len(user_data.get('referrals', []))
    current_level_id, current_level = await utils.get_referral_level(referrals_count)
    referral_link, share_text = await get_referral_link_with_text(user_id)
    
    if not referral_link:
        await callback.answer("Ошибка: не удалось создать ссылку")
        return
    
    message_text = (
        f"🔗 <b>Ваша реферальная ссылка</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        
        f"<b>Ваши текущие условия:</b>\n"
        f"• Уровень: {current_level['name']}\n"
        f"• Процент: {current_level['percent']}%\n"
        f"• Приглашено: {referrals_count} чел.\n\n"
    )
    
    if referrals_count == 0:
        message_text += (
            f"🎁 <b>Специальное предложение для новичков!</b>\n"
            f"Пригласите первого друга и сразу получите:\n"
            f"• Повышение до уровня <b>Легионер</b>\n"
            f"• 20% с каждого платежа\n"
            f"• Старт реферального заработка\n\n"
        )
    
    message_text += (
        f"<b>Текст для отправки друзьям:</b>\n"
        f"<i>{share_text}</i>\n\n"
        
        f"📤 <b>Скопируйте и отправьте друзьям!</b>"
    )
    
    try:
        await callback.message.edit_text(
            message_text,
            reply_markup=get_my_referral_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()
    # ========== ОБРАБОТЧИКИ СИСТЕМЫ РАНГОВ ==========


@dp.callback_query(F.data == "my_current_rank")
async def my_current_rank_handler(callback: CallbackQuery):
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
        
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    completed_tasks = user_data.get('completed_tasks', 0)
    current_rank_id = user_data.get('rank', 'putnik')
    current_rank = await utils.get_rank_info(current_rank_id)
    debts_count = await utils.get_current_debts_count(user_data)
    
    message_text = (
        f"🏆 <b>Твой текущий ранг: {current_rank.get('name', 'Путник')}</b>\n\n"
        f"<b>Твой вызов:</b> {current_rank.get('description', '')}\n\n"
    )
    
    # Показываем привилегии текущего ранга сразу здесь (с ссылками)
    privileges = current_rank.get('privileges', [])
    if privileges:
        message_text += "<b>🎁 Твои привилегии:</b>\n"
        for privilege in privileges:
            message_text += f"• {privilege}\n"
        message_text += "\n"
    
    message_text += f"<b>📊 Твой прогресс:</b>\n"
    message_text += f"• Выполнено заданий: {completed_tasks}/300\n"
    message_text += f"• Текущие долги: {debts_count}\n"
    
    next_rank = await utils.get_next_rank_info(current_rank_id)
    if next_rank:
        tasks_needed = next_rank.get('completed_tasks', 0) - completed_tasks
        message_text += f"• До {next_rank.get('name', 'следующего ранга')}: {tasks_needed} заданий\n"
    
    try:
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboards.get_my_rank_keyboard(),
            disable_web_page_preview=False
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()

@dp.callback_query(F.data == "full_ranks_system")
async def full_ranks_system_handler(callback: CallbackQuery):
    """Показывает полную систему рангов из раздела прогресса"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
        
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    completed_tasks = user_data.get('completed_tasks', 0)
    current_rank_id = user_data.get('rank', 'putnik')
    
    # Получаем информацию о всех рангах с учетом прогресса
    ranks_info = await utils.get_full_ranks_system_info(user_data)
    
    message_text = (
        "<b>🏆 Полная система рангов</b>\n\n"
        "Путь от Путника до Спартанца - 300 выполненных заданий!\n\n"
    )
    
    for rank_id, rank_info in ranks_info:
        min_tasks = rank_info['completed_tasks']
        name = rank_info['name']
        
        # Определяем статус ранга для пользователя
        if rank_info['status'] == 'current':
            status = "<b>ТЕКУЩИЙ РАНГ</b> 🎯"
        elif rank_info['status'] == 'completed':
            status = "✅ Пройден"
        else:
            needed = min_tasks - completed_tasks
            status = f"⏳ Через {needed} заданий"
        
        message_text += f"<b>{name}</b> {status}\n"
        
        # Показываем привилегии для всех рангов
        privileges = rank_info.get('display_privileges', [])
        if privileges:
            for privilege in privileges:
                message_text += f"{privilege}\n"
        
        message_text += "\n"
    
    message_text += (
        f"<b>Твой прогресс:</b> {completed_tasks}/300 выполненных заданий\n"
        f"<b>Текущий ранг:</b> {config.RANKS.get(current_rank_id, {}).get('name', 'Путник')}\n\n"
        f"💪 <b>Выполняй задания чтобы открыть новые привилегии!</b>"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к прогрессу", callback_data="back_to_progress")]
        ]
    )
    
    try:
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            disable_web_page_preview=False  # Разрешаем превью для ссылок
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()
@dp.callback_query(F.data == "back_to_progress")
async def back_to_progress_handler(callback: CallbackQuery):
    """Возврат к прогрессу из системы рангов"""
    if not callback or not callback.from_user:
        return
        
    if callback.message:
        await show_progress_handler(callback)
    else:
        try:
            await callback.answer("Ошибка: сообщение не найдено", show_alert=True)
        except:
            pass
    
    try:
        await callback.answer()
    except:
        pass
@dp.callback_query(F.data == "back_to_main_from_ranks")
async def back_to_main_from_ranks(callback: CallbackQuery):
    """Возврат в главное меню из системы рангов"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    try:
        await callback.message.delete()
        await callback.message.answer(
            "Главное меню:",
            reply_markup=get_main_menu(user.id)
        )
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")
        await callback.answer("Не удалось выполнить действие")
    
    await callback.answer()
@dp.message(Command("rank"))
async def cmd_rank(message: Message):
    """Команда для просмотра текущего ранга"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    completed_tasks = user_data.get('completed_tasks', 0)
    current_rank_id = user_data.get('rank', 'putnik')
    current_rank = await utils.get_rank_info(current_rank_id)
    
    message_text = (
        f"🏆 <b>Твой ранг: {current_rank.get('name', 'Путник')}</b>\n\n"
        f"<b>Твой вызов:</b> {current_rank.get('description', '')}\n\n"
        f"📊 Прогресс: {completed_tasks}/300 выполненных заданий\n"
    )
    # Показываем привилегии
    privileges = current_rank.get('privileges', [])
    if privileges:
        message_text += f"\n<b>🎁 Твои привилегии:</b>\n"
        for privilege in privileges:
            message_text += f"• {privilege}\n"
    
    await message.answer(message_text, reply_markup=get_my_rank_keyboard())
    await utils.update_user_activity(user_id)
    """Команда для просмотра текущего ранга"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    completed_tasks = user_data.get('completed_tasks', 0)
    current_rank_id = user_data.get('rank', 'putnik')
    current_rank = await utils.get_rank_info(current_rank_id)
    
    message_text = (
        f"🏆 <b>Твой ранг: {current_rank.get('name', 'Путник')}</b>\n\n"
        f"📊 Прогресс: {completed_tasks}/300 выполненных заданий\n"
    )
    
    # Показываем привилегии
    privileges = current_rank.get('privileges', [])
    if privileges:
        message_text += f"\n<b>🎁 Твои привилегии:</b>\n"
        for privilege in privileges:
            message_text += f"• {privilege}\n"
    
    await message.answer(message_text, reply_markup=get_my_rank_keyboard())
    await utils.update_user_activity(user_id)
    """Команда для просмотра текущего ранга"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    current_day = user_data.get('current_day', 0)
    current_rank_id = user_data.get('rank', 'putnik')
    current_rank = await utils.get_rank_info(current_rank_id)
    next_rank = await utils.get_next_rank_info(current_rank_id)
    days_to_next = await utils.get_days_until_next_rank(current_rank_id, current_day)
    
    message_text = (
        f"🏆 <b>Твой ранг: {current_rank.get('name', 'Путник')}</b>\n\n"
        f"📊 Прогресс: {current_day}/300 дней\n"
        f"⏭️ Пропусков: {user_data.get('skips_available', 2)}\n"
        f"🔄 Замен: {user_data.get('substitutions_available', 1)}\n\n"
    )
    
    if next_rank and days_to_next > 0:
        message_text += f"🎯 До {next_rank.get('name', 'следующего ранга')}: {days_to_next} дней"
    elif current_rank_id == "legenda":
        message_text += f"🎉 Ты достиг максимального ранга!"
    
    await message.answer(message_text, reply_markup=get_my_rank_keyboard())
    await utils.update_user_activity(user_id)
    # ========== ОБРАБОТЧИКИ РАЗДЕЛА "ПОЛЬЗОВАТЕЛИ" ==========

@dp.callback_query(F.data == "admin_users_list")
async def admin_users_list_handler(callback: CallbackQuery):
    """Список пользователей для админа"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    users = await utils.get_all_users()
    total_users = len(users)
    
    # Сортируем пользователей по дате регистрации (новые первые)
    sorted_users = sorted(users.items(), 
                         key=lambda x: x[1].get('created_at', ''), 
                         reverse=True)
    
    message_text = f"👥 <b>Список пользователей</b>\n\n"
    message_text += f"Всего пользователей: {total_users}\n\n"
    message_text += "<b>Последние 10 пользователей:</b>\n"
    
    for i, (user_id, user_data) in enumerate(sorted_users[:10], 1):
        username = user_data.get('username', 'нет username')
        first_name = user_data.get('first_name', 'Неизвестно')
        archetype = "🛡️" if user_data.get('archetype') == 'spartan' else "⚔️"
        days = user_data.get('current_day', 0)
        
        # Статус подписки
        if await utils.is_subscription_active(user_data):
            status = "💎"
        elif await utils.is_in_trial_period(user_data):
            status = "🆓"
        else:
            status = "❌"
        
        message_text += f"{i}. {status} {archetype} {first_name} - день {days}\n"
        if username != 'нет username':
            message_text += f"   @{username} | ID: {user_id}\n"
        else:
            message_text += f"   ID: {user_id}\n"
    
    if total_users > 10:
        message_text += f"\n... и еще {total_users - 10} пользователей"
    
    from keyboards import get_admin_users_keyboard
    await callback.message.edit_text(message_text, reply_markup=get_admin_users_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_users_search")
async def admin_users_search_handler(callback: CallbackQuery):
    """Поиск пользователя"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    message_text = (
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Для поиска пользователя отправьте:\n"
        "<code>ПОИСК|ID_пользователя</code> - поиск по ID\n"
        "<code>ПОИСК|username</code> - поиск по username\n"
        "<code>ПОИСК|имя</code> - поиск по имени\n\n"
        "<b>Примеры:</b>\n"
        "<code>ПОИСК|123456789</code>\n"
        "<code>ПОИСК|ivanov</code>\n"
        "<code>ПОИСК|Иван</code>"
    )
    
    from keyboards import get_admin_users_keyboard
    await callback.message.edit_text(message_text, reply_markup=get_admin_users_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_users_message")
async def admin_users_message_handler(callback: CallbackQuery):
    """Отправка сообщения пользователю"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    message_text = (
        "✉️ <b>Отправка сообщения пользователю</b>\n\n"
        "Для отправки сообщения пользователю используйте формат:\n"
        "<code>СООБЩЕНИЕ|ID_пользователя|текст сообщения</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>СООБЩЕНИЕ|123456789|Привет! Это тестовое сообщение от администратора.</code>\n\n"
        "⚠️ <b>Внимание:</b> Сообщение будет отправлено сразу!"
    )
    
    from keyboards import get_admin_users_keyboard
    await callback.message.edit_text(message_text, reply_markup=get_admin_users_keyboard())
    await callback.answer()
# ========== ТЕКСТОВЫЕ КОМАНДЫ АДМИНА ==========

@dp.message(F.text.startswith("ПОИСК|"))
async def admin_search_user(message: Message):
    """Обработка поиска пользователя"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    if not message.text:
        await message.answer("❌ Ошибка: текст сообщения пуст")
        return
    
    search_query = message.text.replace("ПОИСК|", "").strip()
    if not search_query:
        await message.answer("❌ Введите поисковый запрос")
        return
    
    users = await utils.get_all_users()
    found_users = []
    
    for user_id, user_data in users.items():
        # Поиск по ID
        if search_query == str(user_id):
            found_users.append((user_id, user_data))
            continue
        
        # Поиск по username
        username = user_data.get('username', '').lower()
        if search_query.lower() in username:
            found_users.append((user_id, user_data))
            continue
        
        # Поиск по имени
        first_name = user_data.get('first_name', '').lower()
        if search_query.lower() in first_name:
            found_users.append((user_id, user_data))
            continue
    
    if not found_users:
        await message.answer(f"❌ Пользователи по запросу '{search_query}' не найдены")
        return
    
    message_text = f"🔍 <b>Результаты поиска:</b> '{search_query}'\n\n"
    message_text += f"Найдено пользователей: {len(found_users)}\n\n"
    
    for i, (user_id, user_data) in enumerate(found_users[:5], 1):
        username = user_data.get('username', 'нет username')
        first_name = user_data.get('first_name', 'Неизвестно')
        archetype = "🛡️" if user_data.get('archetype') == 'spartan' else "⚔️"
        days = user_data.get('current_day', 0)
        
        # Статус подписки
        if await utils.is_subscription_active(user_data):
            status = "💎"
        elif await utils.is_in_trial_period(user_data):
            status = "🆓"
        else:
            status = "❌"
        
        message_text += f"{i}. {status} {archetype} {first_name}\n"
        message_text += f"   ID: {user_id} | День: {days}\n"
        if username != 'нет username':
            message_text += f"   @{username}\n"
        message_text += "\n"
    
    if len(found_users) > 5:
        message_text += f"... и еще {len(found_users) - 5} пользователей"
    
    await message.answer(message_text)

@dp.message(F.text.startswith("СООБЩЕНИЕ|"))
async def admin_send_message(message: Message):
    """Отправка сообщения пользователю"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    if not message.text:
        await message.answer("❌ Ошибка: текст сообщения пуст")
        return
    
    try:
        # Используем безопасное разбиение строки
        text = message.text
        parts = text.split("|") if text else []
        
        if len(parts) < 3:
            await message.answer("❌ Неверный формат. Используйте: СООБЩЕНИЕ|ID|текст")
            return
        
        target_user_id = int(parts[1].strip())
        message_text = "|".join(parts[2:]).strip()
        
        if not message_text:
            await message.answer("❌ Введите текст сообщения")
            return
        
        # Отправляем сообщение пользователю
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"📢 <b>Сообщение от администратора:</b>\n\n{message_text}"
            )
            await message.answer(f"✅ Сообщение отправлено пользователю {target_user_id}")
        except Exception as e:
            await message.answer(f"❌ Не удалось отправить сообщение пользователю {target_user_id}: {e}")
            
    except ValueError:
        await message.answer("❌ Неверный ID пользователя")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(F.text.startswith("РАССЫЛКА|"))
async def admin_broadcast_handler(message: Message):
    """Обработка рассылки"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    if not message.text:
        await message.answer("❌ Ошибка: текст сообщения пуст")
        return
    
    try:
        # Используем безопасное разбиение строки
        text = message.text
        parts = text.split("|") if text else []
        
        if len(parts) < 3:
            await message.answer("❌ Неверный формат. Используйте: РАССЫЛКА|заголовок|текст")
            return
        
        title = parts[1].strip()
        broadcast_text = "|".join(parts[2:]).strip()
        
        if not title or not broadcast_text:
            await message.answer("❌ Введите заголовок и текст рассылки")
            return
        
        users = await utils.get_all_users()
        success_count = 0
        error_count = 0
        
        # Отправляем сообщение о начале рассылки
        progress_msg = await message.answer(f"📢 <b>Начинаем рассылку:</b> {title}\n\nОтправлено: 0/{len(users)}")
        
        for i, (user_id, user_data) in enumerate(users.items(), 1):
            try:
                await bot.send_message(
                    chat_id=int(user_id),
                    text=f"📢 <b>{title}</b>\n\n{broadcast_text}"
                )
                success_count += 1
                
                # Обновляем прогресс каждые 10 сообщений
                if i % 10 == 0:
                    await progress_msg.edit_text(
                        f"📢 <b>Рассылка:</b> {title}\n\n"
                        f"Отправлено: {i}/{len(users)}\n"
                        f"✅ Успешно: {success_count}\n"
                        f"❌ Ошибок: {error_count}"
                    )
                
                # Небольшая задержка чтобы не спамить
                await asyncio.sleep(0.1)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
        
        await progress_msg.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📢 {title}\n"
            f"👥 Всего пользователей: {len(users)}\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {error_count}"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при рассылке: {e}")

@dp.message(F.text.startswith("ЗАДАНИЕ|"))
async def admin_add_task_handler(message: Message):
    """Добавление задания через текстовую команду"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    if not message.text:
        await message.answer("❌ Ошибка: текст сообщения пуст")
        return
    
    try:
        # Используем безопасное разбиение строки
        text = message.text
        parts = text.split("|") if text else []
        
        if len(parts) < 4:
            await message.answer("❌ Неверный формат. Используйте: ЗАДАНИЕ|день|архетип|текст")
            return
        
        day_number = int(parts[1].strip())
        archetype = parts[2].strip().lower()
        task_text = "|".join(parts[3:]).strip()
        
        if archetype not in ['spartan', 'amazon']:
            await message.answer("❌ Неверный архетип. Используйте: spartan или amazon")
            return
        
        if not task_text:
            await message.answer("❌ Введите текст задания")
            return
        
        # Загружаем существующие задания
        tasks = await utils.read_json(config.TASKS_FILE)
        
        # Создаем ID для нового задания
        task_id = f"task_{day_number}_{archetype}"
        
        # Добавляем задание
        tasks[task_id] = {
            'day_number': day_number,
            'archetype': archetype,
            'text': task_text,
            'created_at': datetime.now().isoformat(),
            'created_by': user.id
        }
        
        # Сохраняем задания
        await utils.write_json(config.TASKS_FILE, tasks)
        
        archetype_emoji = "🛡️" if archetype == 'spartan' else "⚔️"
        await message.answer(
            f"✅ <b>Задание добавлено!</b>\n\n"
            f"День: {day_number}\n"
            f"Архетип: {archetype_emoji} {archetype}\n"
            f"Текст: {task_text}"
        )
        
    except ValueError:
        await message.answer("❌ Неверный номер дня")
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении задания: {e}")
    """Обработка рассылки"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    try:
        parts = message.text.split("|")
        if len(parts) < 3:
            await message.answer("❌ Неверный формат. Используйте: РАССЫЛКА|заголовок|текст")
            return
        
        title = parts[1].strip()
        broadcast_text = "|".join(parts[2:]).strip()
        
        if not title or not broadcast_text:
            await message.answer("❌ Введите заголовок и текст рассылки")
            return
        
        users = await utils.get_all_users()
        success_count = 0
        error_count = 0
        
        # Отправляем сообщение о начале рассылки
        progress_msg = await message.answer(f"📢 <b>Начинаем рассылку:</b> {title}\n\nОтправлено: 0/{len(users)}")
        
        for i, (user_id, user_data) in enumerate(users.items(), 1):
            try:
                await bot.send_message(
                    chat_id=int(user_id),
                    text=f"📢 <b>{title}</b>\n\n{broadcast_text}"
                )
                success_count += 1
                
                # Обновляем прогресс каждые 10 сообщений
                if i % 10 == 0:
                    await progress_msg.edit_text(
                        f"📢 <b>Рассылка:</b> {title}\n\n"
                        f"Отправлено: {i}/{len(users)}\n"
                        f"✅ Успешно: {success_count}\n"
                        f"❌ Ошибок: {error_count}"
                    )
                
                # Небольшая задержка чтобы не спамить
                await asyncio.sleep(0.1)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
        
        await progress_msg.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📢 {title}\n"
            f"👥 Всего пользователей: {len(users)}\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {error_count}"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при рассылке: {e}")    

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
# ========== ОБРАБОТЧИКИ ПРОПУСКОВ ЗАДАНИЙ ==========

@dp.callback_query(F.data == "sprint_continue")
async def sprint_continue_handler(callback: CallbackQuery):
    """Обработка продолжения после спринта"""
    user = callback.from_user
    if not user:
        return
        
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        return
    
    # Показываем тариф "пробный за 1 рубль"
    tariff = config.TARIFFS["trial_ruble"]
    
    message_text = (
        "🎉 <b>ОТЛИЧНАЯ РАБОТА!</b>\n\n"
        "Ты завершил 4-дневный спринт и уже прошел 4/300 дней!\n\n"
        "💎 <b>Продолжи путь к сильной версии себя:</b>\n"
        f"• 3 дня пробного периода за 1 рубль\n"
        f"• Затем автоматическая подписка за {config.TARIFFS['month']['price']} руб./месяц\n"
        f"• Отменить можно в любой момент\n\n"
        f"<b>Оплата:</b> {tariff['price']} руб. на карту:\n"
        f"<code>{config.BANK_CARD}</code>\n\n"
        f"После оплаты отправьте скриншот чека в поддержку: {config.SUPPORT_USERNAME}"
    )
    
    try:
        await callback.message.edit_text(message_text)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()
    """Обработка продолжения после спринта"""
    user = callback.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        return
    
    # Показываем тариф "пробный за 1 рубль"
    tariff = config.TARIFFS["trial_ruble"]
    
    message_text = (
        "🎉 <b>ОТЛИЧНАЯ РАБОТА!</b>\n\n"
        "Ты завершил 4-дневный спринт и уже прошел 4/300 дней!\n\n"
        "💎 <b>Продолжи путь к сильной версии себя:</b>\n"
        f"• 3 дня пробного периода за 1 рубль\n"
        f"• Затем автоматическая подписка за {config.TARIFFS['month']['price']} руб./месяц\n"
        f"• Отменить можно в любой момент\n\n"
        f"<b>Оплата:</b> {tariff['price']} руб. на карту:\n"
        f"<code>{config.BANK_CARD}</code>\n\n"
        f"После оплаты отправьте скриншот чека в поддержку: {config.SUPPORT_USERNAME}"
    )
    
    await callback.message.edit_text(message_text)
    await callback.answer()

@dp.callback_query(F.data == "sprint_trial_offer")
async def sprint_trial_offer_handler(callback: CallbackQuery):
    """Обработка принятия предложения"""
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    tariff = config.TARIFFS["trial_ruble"]
    
    message_text = (
        "🎉 <b>Отличный выбор!</b>\n\n"
        f"<b>Ваш специальный тариф:</b>\n"
        f"• 3 дня пробного периода за {tariff['price']} рубль\n"
        f"• Затем автоматическое продление за {tariff['auto_renewal_price']} руб./месяц\n"
        f"• Экономия {config.TARIFFS['month']['price'] - tariff['auto_renewal_price']} рублей!\n\n"
        f"<b>Для активации:</b>\n"
        f"1. Переведите {tariff['price']} руб. на карту:\n"
        f"<code>{config.BANK_CARD}</code>\n"
        f"2. Отправьте скриншот чека в поддержку: {config.SUPPORT_USERNAME}\n\n"
        f"<i>После оплаты мы активируем ваш пробный период и специальную цену!</i>"
    )
    
    try:
        await callback.message.edit_text(message_text)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(message_text)
    
    await callback.answer()

@dp.callback_query(F.data == "sprint_decline")
async def sprint_decline_handler(callback: CallbackQuery):
    """Обработка отказа от предложения"""
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    message_text = (
        "👋 <b>Понимаем, возможно сейчас не лучшее время</b>\n\n"
        "Твой прогресс сохранен - ты на 4/300 дней!\n\n"
        "Если передумаешь - специальное предложение будет ждать тебя в разделе:\n"
        "<b>💎 Моя подписка</b>\n\n"
        "Удачи на пути к сильной версии себя! 💪"
    )
    
    try:
        await callback.message.edit_text(message_text)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer(message_text)
    
    await callback.answer()

# ========== обработчики прогресса и рефералов ==========
@dp.callback_query(F.data == "show_referral_from_progress")
async def show_referral_from_progress(callback: CallbackQuery):
    """Показывает реферальную программу из раздела прогресса"""
    if not callback or not callback.from_user:
        return
        
    if not callback.message:
        try:
            await callback.answer("Ошибка: сообщение не найдено", show_alert=True)
        except:
            pass
        return
        
    user_id = callback.from_user.id
    user_data = await get_user(user_id)
    
    if not user_data:
        try:
            await callback.answer("Сначала зарегистрируйся", show_alert=True)
        except:
            pass
        return
    
    referrals = user_data.get('referrals', [])
    earnings = user_data.get('referral_earnings', 0)
    ref_level_id, ref_level = await get_referral_level(len(referrals))
    
    message_text = (
        f"<b>РЕФЕРАЛЬНАЯ ПРОГРАММА 🤝</b>\n\n"
        f"💫 <b>Приглашай друзей и получай до 50% от их платежей!</b>\n\n"
        f"• Приглашено друзей: {len(referrals)}\n"
        f"• Заработано: {earnings} руб.\n"
        f"• Текущий уровень: {ref_level['name']}\n"
        f"• Ваш процент: {ref_level['percent']}%\n\n"
        f"📤 <b>Просто нажми кнопку ниже чтобы отправить приглашение!</b>"
    )
    
    try:
        await callback.message.edit_text(
            message_text, 
            reply_markup=get_my_referral_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        try:
            await callback.answer("Не удалось обновить сообщение", show_alert=True)
        except:
            pass
    
    try:
        await callback.answer()
    except:
        pass

@dp.callback_query(F.data == "show_subscription_from_progress")
async def show_subscription_from_progress(callback: CallbackQuery):
    """Показывает подписку из раздела прогресса"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    user_id = user.id
    user_data = await get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    message_text = "<b>ПОДПИСКА 💎</b>\n\n"
    
    if await is_subscription_active(user_data):
        try:
            sub_end = datetime.fromisoformat(user_data['subscription_end'])
            days_left = (sub_end - datetime.now()).days
            message_text += f"✅ <b>Статус:</b> Активна ({days_left} дней осталось)\n"
        except:
            message_text += "✅ <b>Статус:</b> Активна\n"
    elif await is_in_trial_period(user_data):
        days_left = await get_trial_days_left(user_data)
        message_text += f"🎁 <b>Статус:</b> Пробный период ({days_left} дней осталось)\n"
    else:
        message_text += "❌ <b>Статус:</b> Не активна\n"
    
    message_text += "\n<b>Доступные тарифы:</b>\n"
    
    for tariff_id, tariff in config.TARIFFS.items():
        message_text += f"• {tariff['name']} - {tariff['price']} руб.\n"
    
    try:
        await callback.message.edit_text(
            message_text, 
            reply_markup=keyboards.get_payment_keyboard()  # УБИРАЕМ user.id
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()


# ========== ПАРНЫХ ТАРИФОВ И ИНВАЙТА ==========
@dp.callback_query(F.data == "activate_invite_from_subscription")
async def activate_invite_from_subscription(callback: CallbackQuery, state: FSMContext):
    """Активация инвайт-кода из раздела подписки"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    await callback.message.edit_text(
        "🎫 <b>Активация инвайт-кода</b>\n\n"
        "Введите инвайт-код для активации подписки:"
    )
    await state.set_state(UserStates.waiting_for_invite)

@dp.callback_query(F.data == "activate_subscription_after_trial")
async def activate_subscription_after_trial(callback: CallbackQuery):
    """Активация подписки после пробного периода"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    try:
        await callback.message.edit_text(
            "<b>ПОДПИСКА 💎</b>\n\n"
            "Выбери подходящий тариф чтобы продолжить получать задания:",
            reply_markup=keyboards.get_payment_keyboard()  # УБИРАЕМ user.id
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()

async def show_progress_handler(update):
    """Показывает полную информацию о прогрессе, ранге и привилегиями через кнопки"""
    # Определяем тип обновления и получаем необходимые объекты
    if isinstance(update, CallbackQuery):
        user = update.from_user if update.from_user else None
        message_obj = update.message if update.message else None
        is_callback = True
    elif isinstance(update, Message):
        user = update.from_user if update.from_user else None
        message_obj = update
        is_callback = False
    else:
        return

    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        if is_callback:
            try:
                if update:
                    await update.answer("Сначала зарегистрируйся через /start", show_alert=True)
            except Exception as e:
                logger.error(f"Ошибка при ответе на callback: {e}")
        else:
            if message_obj:
                await message_obj.answer("Сначала зарегистрируйся через /start")
        return
    
    completed_tasks = user_data.get('completed_tasks', 0)
    current_rank = user_data.get('rank', 'putnik')
    rank_info = await utils.get_rank_info(current_rank)
    postponed_count = await utils.get_current_postponed_count(user_data)
    # Получаем информацию о следующем ранге
    next_rank = await utils.get_next_rank_info(current_rank)
    tasks_to_next_rank = await utils.get_tasks_until_next_rank(current_rank, completed_tasks)
    
    # Простой и понятный текст прогресса
    message_text = (
        f"<b>📊 ТВОЙ ПРОГРЕСС</b>\n\n"
        
        f"<b>🏆 Ранг:</b> {rank_info.get('name', 'Путник')}\n"
        f"<b>✅ Выполнено:</b> {completed_tasks}/300 заданий\n"
        f"<b>⏰ Отложенные задания:</b> {postponed_count}\n"
    )
    
    # Процент прогресса
    progress_percent = min(100, (completed_tasks / 300) * 100)
    message_text += f"<b>📈 Прогресс:</b> {progress_percent:.1f}%\n\n"
    
    # Информация о следующем ранге
    if next_rank and tasks_to_next_rank > 0:
        message_text += f"<b>🎯 До {next_rank.get('name', 'следующего ранга')}:</b> {tasks_to_next_rank} заданий\n\n"
    elif current_rank == "spartan":
        message_text += f"<b>🎉 Поздравляем! Ты достиг максимального ранга!</b>\n\n"
    
    # Описание ранга
    description = rank_info.get('description', '').replace("Твой вызов: ", "")
    if description:
        message_text += f"<b>💡 {description}</b>\n\n"
    
    # Привилегии - просто перечисляем названия
    privileges_with_links = await utils.get_privileges_with_links(current_rank, user_data)
    if privileges_with_links:
        message_text += "<b>🎁 Твои привилегии:</b>\n"
        for i, (privilege, link) in enumerate(privileges_with_links, 1):
            message_text += f"{i}. {privilege}\n"
        message_text += "\n"
    
    # Предупреждение о долгах
    if postponed_count > 0:
        message_text += f"<b>⚠️ У тебя {postponed_count} отложенных заданий!</b>\n"
        message_text += "Они вернутся после 300 задания.\n\n"
    
    # Мотивационное сообщение
    if completed_tasks == 0:
        message_text += "🚀 <b>Ты в начале пути! Первые шаги самые важные.</b>"
    elif completed_tasks < 30:
        message_text += "💪 <b>Отличное начало! Продолжай в том же духе!</b>"
    elif completed_tasks < 100:
        message_text += "🔥 <b>Ты набираешь обороты! Дисциплина становится твоей привычкой.</b>"
    elif completed_tasks < 200:
        message_text += "🌟 <b>Впечатляющие результаты! Ты уже прошел большую часть пути.</b>"
    else:
        message_text += "👑 <b>Невероятно! Ты почти у цели! Осталось совсем немного.</b>"
    
    # Создаем клавиатуру с кнопками для привилегий
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Основные кнопки навигации
    keyboard_buttons = [
        [InlineKeyboardButton(text="📊 Полная система рангов", callback_data="full_ranks_system")],
        [InlineKeyboardButton(text="🤝 Реферальная программа", callback_data="show_referral_from_progress")],
        [InlineKeyboardButton(text="💎 Моя подписка", callback_data="show_subscription_from_progress")]
    ]
    
    # Добавляем кнопки для привилегий (если есть привилегии со ссылками)
    # Добавляем кнопки для привилегий (если есть привилегии со ссылками)
    privilege_buttons = []
    for privilege, link in privileges_with_links:
        if link:  # Если есть ссылка для этой привилегии
            # Сопоставляем привилегии с нужными названиями кнопок
            button_text = "🔗 "
            if "Бесплатный канал 300 ПИНКОВ" in privilege:
                button_text += "300 ПИНКОВ"
            elif "Набор эксклюзивных стикеров для мотивации" in privilege:
                button_text += "СТИКЕР-ПИНКИ"
            elif "Возможность предлагать свои задания для системы" in privilege:
                button_text += "ПРЕДЛОЖИТЬ ПИНОК"
            elif "Бесплатный доступ в закрытую группу" in privilege:
                button_text += "ПРЕМИУМ ГРУППА"
            else:
                button_text += privilege  # На всякий случай оставляем оригинальное название
                
            privilege_buttons.append([InlineKeyboardButton(text=button_text, url=link)])
    
    # Добавляем кнопки привилегий перед основными кнопками
    if privilege_buttons:
        keyboard_buttons = privilege_buttons + keyboard_buttons
    
    progress_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    if is_callback:
        if update and update.message:
            try:
                await update.message.edit_text(
                    message_text, 
                    reply_markup=progress_keyboard,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                try:
                    if update:
                        await update.answer("Не удалось обновить сообщение", show_alert=True)
                except Exception as e2:
                    logger.error(f"Ошибка при ответе на callback: {e2}")
    else:
        if message_obj:
            await message_obj.answer(
                message_text, 
                reply_markup=progress_keyboard,
                disable_web_page_preview=True
            )
    
    if user_id:
        await utils.update_user_activity(user_id)

@dp.message(F.text == "Мой прогресс 🏆")
async def show_progress_message(message: Message):
    """Показывает прогресс для текстового сообщения"""
    if message and message.from_user:
        await show_progress_handler(message)

@dp.callback_query(F.data == "tariff_pair_year")
async def process_pair_year(callback: CallbackQuery):
    """Обработка выбора парной годовой подписки"""
    if not callback.data:
        await callback.answer("Ошибка: данные не найдены")
        return
        
    tariff_id = "pair_year"
    tariff = config.TARIFFS.get(tariff_id)
    
    if not tariff:
        await callback.answer("Тариф не найден")
        return
    
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
    
    message_text = (
        f"<b>Оплата парной годовой подписки</b>\n\n"
        f"👥 <b>Это парная подписка на двух человек!</b>\n\n"
        f"Сумма к оплате: {tariff['price']} руб.\n"
        f"Срок действия: {tariff['days']} дней\n\n"
        
        f"<b>После оплаты:</b>\n"
        f"1. Отправьте скриншот чека в поддержку\n"
        f"2. Укажите username второго участника\n"
        f"3. Мы активируем подписку вам обоим\n\n"
        
        f"<b>Для оплаты переведите сумму на карту:</b>\n"
        f"<code>{config.BANK_CARD}</code>\n\n"
        f"После оплаты отправьте скриншот чека в поддержку: {config.SUPPORT_USERNAME}"
    )
    
    try:
        await callback.message.edit_text(message_text)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()

@dp.message(F.text == "🔙 Назад к заданию")
async def back_to_task(message: Message):
    """Возврат к текущему заданию"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    # Показываем текущее задание
    await show_todays_task(message)
    
# ========== ТЕСТ РАНГОВ ==========
@dp.message(Command("test_ranks"))
async def test_ranks_command(message: Message):
    """Быстрое переключение между рангами для тестирования"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    from keyboards import get_test_ranks_keyboard
    
    await message.answer(
        "🎯 <b>ТЕСТИРОВАНИЕ СИСТЕМЫ РАНГОВ</b>\n\n"
        "Выбери ранг для тестирования. Твой текущий прогресс будет временно изменен.\n"
        "Для возврата к реальному прогрессу используй команду /reset_test_rank",
        reply_markup=get_test_ranks_keyboard()
    )    

@dp.callback_query(F.data.startswith("test_rank_"))
async def test_rank_handler(callback: CallbackQuery):
    """Установка тестового ранга"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
    
    if not callback.data:
        await callback.answer("Ошибка данных")
        return
    
    rank_id = callback.data.replace("test_rank_", "")
    rank_info = await utils.get_rank_info(rank_id)
    
    if not rank_info:
        await callback.answer("❌ Ранг не найден")
        return
    
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Сохраняем реальный прогресс если это первый тест
    if 'real_progress' not in user_data:
        user_data['real_progress'] = {
            'completed_tasks': user_data.get('completed_tasks', 0),
            'rank': user_data.get('rank', 'putnik'),
            'current_day': user_data.get('current_day', 0)
        }
    
    # Устанавливаем тестовые значения для выбранного ранга
    target_tasks = rank_info.get('completed_tasks', 0)
    user_data['completed_tasks'] = target_tasks
    user_data['rank'] = rank_id
    user_data['current_day'] = target_tasks  # Синхронизируем день с выполненными заданиями
    
    await utils.save_user(user_id, user_data)
    
    await callback.message.edit_text(
        f"✅ <b>Установлен тестовый ранг: {rank_info.get('name', 'Неизвестно')}</b>\n\n"
        f"📊 Выполнено заданий: {target_tasks}/300\n"
        f"🏆 Ранг: {rank_info.get('name', 'Неизвестно')}\n\n"
        f"<i>Для возврата к реальному прогрессу используй /reset_test_rank</i>",
        reply_markup=keyboards.get_test_ranks_keyboard()
    )
    await callback.answer()

@dp.message(Command("reset_test_rank"))
async def reset_test_rank_command(message: Message):
    """Сброс тестового ранга и возврат к реальному прогрессу"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Пользователь не найден")
        return
    
    if 'real_progress' not in user_data:
        await message.answer("ℹ️ Тестовый режим не активен. Твой прогресс реальный.")
        return
    
    # Восстанавливаем реальный прогресс
    real_progress = user_data['real_progress']
    user_data['completed_tasks'] = real_progress['completed_tasks']
    user_data['rank'] = real_progress['rank']
    user_data['current_day'] = real_progress['current_day']
    
    # Удаляем временные данные
    del user_data['real_progress']
    
    await utils.save_user(user_id, user_data)
    
    current_rank_info = await utils.get_rank_info(real_progress['rank'])
    
    await message.answer(
        f"🔄 <b>Реальный прогресс восстановлен!</b>\n\n"
        f"📊 Выполнено заданий: {real_progress['completed_tasks']}/300\n"
        f"🏆 Ранг: {current_rank_info.get('name', 'Неизвестно')}\n\n"
        f"Теперь ты снова в боевом режиме! 💪"
    )

@dp.callback_query(F.data == "test_rank_reset")
async def test_rank_reset_handler(callback: CallbackQuery):
    """Обработчик кнопки сброса тестового режима"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
        
    # Просто вызываем команду сброса
    await reset_test_rank_command(callback.message)
    await callback.answer()
@dp.message(F.text == "🎯 Тест рангов")
async def test_ranks_button(message: Message):
    """Кнопка тестирования рангов в админ-панели"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    await test_ranks_command(message)
# ========== ОБРАБОТЧИКИ "ПИНОК ДРУГУ" ==========
@dp.message(F.text == "📤 Пинок другу")
async def send_pink_to_friend_during_task(message: Message):
    """Отправка текущего пинка другу во время выполнения задания - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала зарегистрируйся через /start")
        return
    
    try:
        # Получаем текущее задание пользователя
        todays_tasks = await utils.get_todays_tasks(user_data)
        
        if not todays_tasks:
            await message.answer(
                "❌ <b>Нет активных заданий для отправки</b>\n\n"
                "Возможно:\n"
                "• Ты уже выполнил сегодняшнее задание\n" 
                "• Подписка не активна\n"
                "• Задание еще не пришло\n\n"
                "Проверь статус подписки или подожди до завтрашнего задания!",
                reply_markup=keyboards.get_main_menu(user_id)
            )
            return
        
        current_task = todays_tasks[0]
        
        # БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ДАННЫХ ЗАДАНИЯ
        task_day = current_task.get('day', 1)
        
        # Получаем текст задания из разных возможных мест
        task_text = "Текст задания не найден"
        if 'text' in current_task:
            task_text = current_task['text']
        elif 'data' in current_task and 'text' in current_task['data']:
            task_text = current_task['data']['text']
        
        logger.info(f"📤 Пользователь {user_id} отправляет пинок дня {task_day}")
        
        # Получаем username бота для inline режима
        bot_username = (await bot.get_me()).username
        if not bot_username:
            await message.answer(
                "❌ <b>Ошибка: у бота не установлен username</b>\n\n"
                "Для работы функции отправки пинков боту нужен username. "
                "Обратитесь к администратору."
            )
            return
        
        await message.answer(
            f"🎯 <b>Отправить текущий пинок другу</b>\n\n"
            f"<b>Твой пинок дня #{task_day}:</b>\n"
            f"«{task_text}»\n\n"
            f"📱 <b>Как отправить:</b>\n"
            f"1. Нажми кнопку «📤 Отправить другу» ниже\n" 
            f"2. Выбери друга из списка контактов\n"
            f"3. Отправь сообщение\n\n"
            f"<i>Друг получит твое задание и сможет попробовать челлендж!</i>",
            reply_markup=keyboards.get_current_pink_keyboard(task_day)
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в send_pink_to_friend_during_task: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка при подготовке пинка</b>\n\n"
            "Мы уже работаем над исправлением этой проблемы. "
            "Попробуй позже или используй команду /debug_pink для диагностики.",
            reply_markup=keyboards.get_main_menu(user_id)
        )
    
    await utils.update_user_activity(user_id)

@dp.message(F.text == "🔙 Назад")
async def back_to_task_handler(message: Message):
    """Обработчик кнопки Назад во время выполнения задания"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    # Показываем текущее задание
    await show_todays_task(message)


@dp.message(F.text == "📤 Пинок другу")
async def send_to_friend_main_menu(message: Message):
    """Пинок другу из главного меню"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    current_day = user_data.get('current_day', 0)
    
    if current_day == 0:
        # Если нет выполненных заданий
        await message.answer(
            "📤 <b>Пинок другу</b>\n\n"
            "Пригласи друга в челлендж «300 ПИНКОВ»!\n\n"
            "Выбери способ отправки:",
            reply_markup=keyboards.get_send_to_friend_keyboard()
        )
    else:
        # Если есть выполненные задания
        await message.answer(
            "🎯 <b>Пинок другу</b>\n\n"
            "Отправь другу одно из своих выполненных заданий!\n"
            "Он получит пробное задание и сможет присоединиться к челленджу.\n\n"
            f"Ты выполнил уже {current_day} пинков!",
            reply_markup=keyboards.get_pink_list_keyboard(user_data)
        )
    
    await utils.update_user_activity(user_id)

@dp.callback_query(F.data == "back_to_task")
async def back_to_task_callback(callback: CallbackQuery):
    """Возврат к заданию из inline клавиатуры"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    if not callback.message:
        await callback.answer("Ошибка")
        return
        
    try:
        await callback.message.delete()
        # Показываем задание снова
        user_id = user.id
        user_data = await utils.get_user(user_id)
        
        if user_data:
            todays_tasks = await utils.get_todays_tasks(user_data)
            if todays_tasks:
                await show_todays_task(callback)
            else:
                await callback.message.answer(
                    "❌ Нет активных заданий",
                    reply_markup=keyboards.get_main_menu(user_id)
                )
    except Exception as e:
        logger.error(f"Ошибка при возврате к заданию: {e}")
        await callback.answer("Не удалось вернуться к заданию")
    
    await callback.answer()


@dp.callback_query(F.data.startswith("copy_current_pink_"))
async def copy_current_pink_link(callback: CallbackQuery):
    """Копирование текста текущего пинка вместо создания ссылки"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
        
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено")
        return
        
    if not callback.data:
        await callback.answer("❌ Ошибка данных")
        return
        
    try:
        pink_day_str = callback.data.replace("copy_current_pink_", "")
        pink_day = int(pink_day_str) if pink_day_str.isdigit() else 0
        
        user_data = await utils.get_user(user.id)
        
        if user_data and pink_day > 0:
            # Получаем задание для этого дня
            task_id, task = await utils.get_task_by_day(pink_day, user_data['archetype'])
            
            if task:
                # Формируем текст для копирования
                pink_text = (
                    f"🎯 Пинок дня #{pink_day} от {user.first_name}:\n\n"
                    f"«{task['text']}»\n\n"
                    f"💪 Из челленджа «300 ПИНКОВ»"
                )
                
                await callback.answer(f"📋 Текст пинка скопирован!", show_alert=True)
            else:
                await callback.answer("❌ Задание не найдено")
        else:
            await callback.answer("❌ Ошибка данных")
            
    except ValueError:
        await callback.answer("❌ Неверный номер дня")
    except Exception as e:
        logger.error(f"Ошибка при копировании пинка: {e}")
        await callback.answer("❌ Ошибка при копировании")

@dp.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    """Упрощенный обработчик inline запросов"""
    user_id = inline_query.from_user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        return
    
    bot_username = (await bot.get_me()).username
    results = []
    
    query = inline_query.query or ""
    
    # ПРИГЛАШЕНИЕ В ЧЕЛЛЕНДЖ
    if query == "invite":
        message_text = (
            f"💎 <b>Привет! Хочу поделиться с тобой крутым инструментом</b>\n\n"
            
            f"Я начал(а) проходить челлендж «300 ПИНКОВ» - это не просто бот, а настоящая система "
            f"прокачки силы воли и дисциплины.\n\n"
            
            f"🎯 <b>Что это такое?</b>\n"
            f"• Ежедневные задания, которые заставляют мозг работать по-новому\n"
            f"• Никакой мотивации - только система и дисциплина\n"
            f"• 300 дней непрерывного роста и изменений\n\n"
            
            f"Я уже в процессе и чувствую, как меняется мое мышление и дисциплина.\n"
            f"Присоединяйся - давай расти вместе! 🌱\n\n"
            
            f"👉 <b>Начать челлендж:</b> https://t.me/{bot_username}?start={user_id}"
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        results.append(
            InlineQueryResultArticle(
                id="referral_invite",
                title="💎 Приглашение в челлендж",
                description="Отправить красивое приглашение другу",
                input_message_content=InputTextMessageContent(
                    message_text=message_text,
                    parse_mode="HTML"
                ),
                thumb_url="https://img.icons8.com/fluency/96/000000/invite.png",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(
                            text="🚀 Начать челлендж", 
                            url=f"https://t.me/{bot_username}?start={user_id}"
                        )
                    ]]
                )
            )
        )
    
    # ТЕКУЩИЙ ПИНОК
    elif query == "":
        todays_tasks = await utils.get_todays_tasks(user_data)
        
        if todays_tasks:
            # Есть текущее задание - отправляем текущий пинок
            current_task = todays_tasks[0]
            task_day = current_task['day']
            task_text = current_task['text']
            
            message_text = (
                f"🎯 <b>Пинок от {inline_query.from_user.first_name}</b>\n\n"
                f"«{task_text}»\n\n"
                f"💪 Это мое текущее задание из челленджа «300 ПИНКОВ»!\n"
                f"Присоединяйся и начни свой путь к силе воли.\n\n"
                f"🚀 Начать: https://t.me/{bot_username}?start={user_id}"
            )
            
            results.append(
                InlineQueryResultArticle(
                    id="current_pink",
                    title="📤 Текущий пинок",
                    description=f"День #{task_day}: {task_text[:50]}...",
                    input_message_content=InputTextMessageContent(
                        message_text=message_text,
                        parse_mode="HTML"
                    ),
                    thumb_url="https://img.icons8.com/fluency/96/000000/fitness.png"
                )
            )
    
    if results:
        await inline_query.answer(results, cache_time=1, is_personal=True)


# В конец bot.py можно добавить обработчик вебхуков
@dp.message(F.text == "/webhook")
async def setup_webhook(message: Message):
    """Команда для настройки вебхука (для админа)"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    # Здесь можно добавить логику настройки вебхука
    await message.answer("Вебхук для ЮKassa можно настроить через панель администратора ЮKassa")

async def main():
    logger.info("Бот запускается...")
    
    # ТЕСТ: Принудительно запускаем рассылку при старте
    logger.info("🔄 Принудительный запуск рассылки при старте...")
    await send_daily_tasks()
    
    # Запускаем планировщик
    scheduler.add_job(
        send_daily_tasks,
        trigger=CronTrigger(
            hour=config.TASK_TIME_HOUR,
            minute=config.TASK_TIME_MINUTE,
            timezone=config.TIMEZONE
        ),
        id="daily_tasks"
    )
    
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(
            hour=config.REMINDER_TIME_HOUR,
            minute=config.REMINDER_TIME_MINUTE,
            timezone=config.TIMEZONE
        ),
        id="reminders"
    )
    
    scheduler.add_job(
        check_midnight_reset,
        trigger=CronTrigger(
            hour=0, minute=0,  # Полночь
            timezone=config.TIMEZONE
        ),
        id="midnight_reset"
    )
    
    scheduler.start()
    logger.info("📅 Планировщик запущен")
    
    await dp.start_polling(bot)
    logger.info("Бот запускается...")
    await dp.start_polling(bot)
    logger.info("Бот запускается...")
    
    # Запускаем планировщик
    scheduler.add_job(
        send_daily_tasks,
        trigger=CronTrigger(
            hour=config.TASK_TIME_HOUR,
            minute=config.TASK_TIME_MINUTE,
            timezone=config.TIMEZONE
        ),
        id="daily_tasks"
    )
    
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(
            hour=config.REMINDER_TIME_HOUR,
            minute=config.REMINDER_TIME_MINUTE,
            timezone=config.TIMEZONE
        ),
        id="reminders"
    )
    
    scheduler.add_job(
        check_midnight_reset,
        trigger=CronTrigger(
            hour=0, minute=0,  # Полночь
            timezone=config.TIMEZONE
        ),
        id="midnight_reset"
    )
    
    scheduler.start()
    logger.info("📅 Планировщик запущен")
    
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())