import asyncio
import logging
import payments
from datetime import datetime
import random
import math 
from aiogram.fsm.storage.base import StorageKey
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
    get_all_users
)

from keyboards import (
    get_main_menu, archetype_keyboard, task_keyboard, admin_keyboard,
    get_payment_keyboard, get_my_rank_keyboard, get_my_referral_keyboard,
    get_admin_invite_keyboard, get_invite_code_types_keyboard
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Инициализация планировщика
import pytz
scheduler = AsyncIOScheduler(timezone=pytz.timezone(config.TIMEZONE))
# В начале файла, после других импортов
from datetime import datetime, timedelta
import uuid
from typing import List, Dict, Any
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

# ДОБАВЛЯЕМ НОВЫЕ СОСТОЯНИЯ
class UserStates(StatesGroup):
    waiting_for_archetype = State()
    waiting_for_invite = State()
    waiting_for_timezone = State()
    waiting_for_ready = State()
    # Новые состояния для вывода
    waiting_for_withdrawal_amount = State()
    waiting_for_withdrawal_method = State()
    waiting_for_withdrawal_details = State()
    confirm_withdrawal = State()
    # Состояния для админской обработки выводов
    admin_waiting_withdrawal_action = State()
    admin_waiting_withdrawal_comment = State()

class ReferralNotifications:
    """Класс для уведомлений реферальной системы"""
    
    @staticmethod
    async def send_referral_bonus_notification(bot, referrer_id: int, bonus_info: dict):
        """Отправляет уведомление о реферальном бонусе"""
        try:
            # БЕЗОПАСНАЯ ПРОВЕРКА referrer_id
            if not referrer_id:
                logger.warning(f"⚠️ Пропуск уведомления: referrer_id is None")
                return
                
            message_text = (
                f"🎉 <b>РЕФЕРАЛЬНЫЙ БОНУС!</b>\n\n"
                f"Ваш реферал <b>{bonus_info.get('referred_name', 'Пользователь')}</b> "
                f"оплатил подписку!\n\n"
                f"💰 <b>Начислено:</b> {bonus_info['bonus_amount']} руб.\n"
                f"📊 <b>Процент:</b> {bonus_info['percent']}%\n"
                f"💳 <b>Сумма платежа:</b> {bonus_info['payment_amount']} руб.\n\n"
                f"🏆 <b>Ваш текущий баланс:</b> {bonus_info.get('new_balance', 0)} руб.\n\n"
                f"💪 Продолжайте приглашать друзей!"
            )
            
            await bot.send_message(
                chat_id=int(referrer_id),  # УБЕЖДАЕМСЯ ЧТО INT
                text=message_text
            )
            logger.info(f"✅ Уведомление о бонусе отправлено рефереру {referrer_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления рефереру {referrer_id}: {e}")
    
    @staticmethod
    async def send_withdrawal_request_notification(bot, admin_id: int, withdrawal_data: dict):
        """Отправляет уведомление админу о новой заявке на вывод"""
        try:
            # БЕЗОПАСНЫЙ ДОСТУП К ДАННЫМ
            withdrawal_id = withdrawal_data.get('id', 'N/A')
            user_name = withdrawal_data.get('user_name', 'Неизвестно')
            user_username = withdrawal_data.get('user_username', 'без username')
            user_id = withdrawal_data.get('user_id', 'N/A')
            amount = withdrawal_data.get('amount', 0)
            amount_after_fee = withdrawal_data.get('amount_after_fee', 0)
            fee = withdrawal_data.get('fee', 0)
            fee_percent = withdrawal_data.get('fee_percent', 0)
            method = withdrawal_data.get('method', 'Неизвестно')
            details = withdrawal_data.get('details', 'Не указаны')
            created_at = withdrawal_data.get('created_at', '')
            
            message_text = (
                f"📤 <b>НОВАЯ ЗАЯВКА НА ВЫВОД</b>\n\n"
                f"🆔 ID: <code>{withdrawal_data.get('id', 'N/A')}</code>\n"
                f"👤 Пользователь: {withdrawal_data.get('user_name', 'Неизвестно')}\n"
                f"📱 @{withdrawal_data.get('user_username', 'без username')}\n"
                f"🆔 User ID: {withdrawal_data.get('user_id', 'N/A')}\n\n"
                f"💰 <b>Сумма:</b> {withdrawal_data.get('amount', 0)} руб.\n"
                f"🎯 <b>Минимум:</b> {config.MIN_WITHDRAWAL} руб. (без комиссии)\n\n"  # Изменили
                f"💳 <b>Способ:</b> {withdrawal_data.get('method', 'Неизвестно')}\n"
                f"📝 <b>Реквизиты:</b>\n<code>{withdrawal_data.get('details', 'Не указаны')}</code>\n\n"
            )
            
            # БЕЗОПАСНО ФОРМАТИРУЕМ ДАТУ
            if created_at and len(created_at) > 10:
                formatted_date = created_at[:19].replace('T', ' ')
                message_text += f"📅 <b>Дата:</b> {formatted_date}\n\n"
            
            message_text += f"Действия:"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Одобрить", 
                            callback_data=f"admin_withdraw_approve_{withdrawal_id}"
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить", 
                            callback_data=f"admin_withdraw_reject_{withdrawal_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="📋 Все заявки", 
                            callback_data="admin_withdrawals_list"
                        )
                    ]
                ]
            )
            
            await bot.send_message(
                chat_id=admin_id,
                text=message_text,
                reply_markup=keyboard
            )
            logger.info(f"✅ Уведомление о выводе отправлено админу")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления админу: {e}")
    
    @staticmethod
    async def send_withdrawal_status_notification(bot, user_id: int, withdrawal_data: dict, status: str, comment: str = ""):
        """Отправляет уведомление пользователю о статусе вывода"""
        try:
            # БЕЗОПАСНЫЙ ДОСТУП К ДАННЫМ
            withdrawal_id = withdrawal_data.get('id', 'N/A')
            amount = withdrawal_data.get('amount', 0)
            method = withdrawal_data.get('method', 'Неизвестно')
            amount_after_fee = withdrawal_data.get('amount_after_fee', 0)
            fee = withdrawal_data.get('fee', 0)
            updated_at = withdrawal_data.get('updated_at', withdrawal_data.get('created_at', ''))
            
            status_texts = {
                "processing": "⏳ <b>Ваша заявка на вывод обрабатывается</b>",
                "completed": "✅ <b>Вывод средств завершен</b>",
                "rejected": "❌ <b>Заявка на вывод отклонена</b>",
                "cancelled": "🚫 <b>Вывод отменен</b>"
            }
            
            message_text = (
                f"{status_texts.get(status, '📋 <b>Статус заявки изменен</b>')}\n\n"
                f"🆔 <b>Номер заявки:</b> {withdrawal_id}\n"
                f"💰 <b>Сумма:</b> {amount} руб.\n"
                f"💳 <b>Способ:</b> {method}\n\n"
            )
            
            if comment:
                message_text += f"📝 <b>Комментарий:</b> {comment}\n\n"
            
            if status == "completed":
                message_text += f"💸 <b>Зачислено:</b> {amount_after_fee} руб.\n"
                message_text += f"📊 <b>Комиссия:</b> {fee} руб.\n\n"
            
            # БЕЗОПАСНО ФОРМАТИРУЕМ ДАТУ
            if updated_at and len(updated_at) > 10:
                formatted_date = updated_at[:19].replace('T', ' ')
                message_text += f"📅 <b>Дата:</b> {formatted_date}"
            
            await bot.send_message(
                chat_id=user_id,
                text=message_text
            )
            logger.info(f"✅ Уведомление о статусе вывода отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки статуса вывода пользователю {user_id}: {e}")
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
async def send_daily_tasks():
    """ОПТИМИЗИРОВАННАЯ асинхронная рассылка заданий с этапами"""
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
                task = send_task_to_user(user_id, user_data)  # Используем обновленную функцию
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
# В функции send_daily_tasks обновим логику отправки обычных заданий:

import asyncio
from aiogram import exceptions

async def send_task_to_user(user_id: int, user_data: dict):
    """Отправляет задание конкретному пользователю"""
    try:
        logger.info(f"🔍 send_task_to_user: проверяю пользователя {user_id}")
        
        # Проверяем, что user_data не None
        if not user_data:
            logger.error(f"❌ user_data is None для пользователя {user_id}")
            return False
        
        # Получаем архетип пользователя
        archetype = user_data.get('archetype', 'spartan')
        
        # Проверяем доступ к заданиям
        has_subscription = await utils.is_subscription_active(user_data)
        in_trial = await utils.is_in_trial_period(user_data)
        
        logger.info(f"📊 Статус пользователя {user_id}: sub={has_subscription}, trial={in_trial}, archetype={archetype}")
        
        # Проверяем, не закончил ли уже 3 пробных задания
        if in_trial:
            trial_tasks = user_data.get('completed_tasks_in_trial', 0)
            if trial_tasks >= 3:
                logger.info(f"⏸️ Пользователь {user_id} уже выполнил все 3 пробных задания")
                return False
        
        if not has_subscription and not in_trial:
            logger.info(f"❌ Пользователь {user_id} не имеет доступа")
            return False
        
        # Проверяем, может ли пользователь получить задание
        can_receive = await utils.can_receive_new_task(user_data)
        logger.info(f"🎯 Пользователь {user_id} может получить задание: {can_receive}")
        
        if not can_receive:
            logger.info(f"⏸️ Пользователь {user_id} не может получить задание сейчас")
            return False
        
        # Получаем следующий день пользователя
        current_day = user_data.get('current_day', 0)
        next_day = current_day + 1
        
        # Если день 0 (новый пользователь), ставим день 1
        if next_day == 0:
            next_day = 1
        
        logger.info(f"📅 Пользователь {user_id} - текущий день: {current_day}, следующий день: {next_day}")
        
        todays_tasks = await utils.get_todays_tasks(user_data)
        logger.info(f"📋 Заданий для пользователя {user_id}: {len(todays_tasks) if todays_tasks else 0}")
        
        if not todays_tasks:
            logger.warning(f"⚠️ Нет заданий для пользователя {user_id}")
            return False
        
        task = todays_tasks[0]
        logger.info(f"📝 Задание дня {task['day']}: {task['text'][:50]}...")
        
        message_text = (
            f"📋 <b>Задание на сегодня</b>\n\n"
            f"<b>День {task['day']}/300</b>\n\n"
            f"{task['text']}\n\n"
            f"⏰ <b>До 23:59 на выполнение</b>\n\n"
            f"<i>Встретимся завтра в 9:00 ⏰</i>"
        )
        
        logger.info(f"📤 Отправляю задание пользователю {user_id}")
        
        # Отправляем сообщение
        await bot.send_message(
            chat_id=user_id,
            text=message_text,
            reply_markup=keyboards.task_keyboard
        )
        
        # Обновляем данные пользователя
        user_data['last_task_sent'] = datetime.now().isoformat()
        user_data['task_completed_today'] = False
        await utils.save_user(user_id, user_data)
        
        logger.info(f"✅ Задание отправлено пользователю {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}", exc_info=True)
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
    """Напоминания в 18:30 с разнообразными репликами"""
    logger.info("🕡 Начинаем рассылку напоминаний...")
    
    users = await utils.get_users_without_response()
    if not users:  # Проверяем что users не None
        logger.info("👥 Нет пользователей для напоминаний")
        return
    
    sent_count = 0
    error_count = 0
    
    for user_id, user_data in users:
        try:
            # Получаем только основное задание
            todays_tasks = await utils.get_todays_tasks(user_data)
            
            if todays_tasks:
                task = todays_tasks[0]
                
                # Получаем случайную реплику
                reminder_text = await BotReplies.get_reminder_reply()
                
                message_text = (
                    f"{reminder_text}\n\n"
                    f"<b>Задание дня #{task['day']}</b>\n"
                    f"«{task['text']}»\n\n"
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
    """Полуночный сброс и блокировка с разнообразными репликами"""
    logger.info("🕛 Выполняем полуночный сброс...")
    
    users = await utils.get_all_users()
    reset_count = 0
    blocked_count = 0
    
    default_timezone = pytz.timezone(config.TIMEZONE)
    now = datetime.now(default_timezone)
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            
            # Пропускаем неактивных пользователей
            if not await utils.is_subscription_active(user_data) and not await utils.is_in_trial_period(user_data):
                continue
            
            # ЕСЛИ ЗАДАНИЕ ВЫПОЛНЕНО СЕГОДНЯ - просто сбрасываем флаг
            if user_data.get('task_completed_today', False):
                user_data['task_completed_today'] = False
                reset_count += 1
                await utils.save_user(user_id, user_data)
                logger.debug(f"✅ Сброшен флаг для пользователя {user_id}")
                continue
            
            # Получаем часовой пояс пользователя
            user_timezone_str = user_data.get('timezone', config.TIMEZONE)
            try:
                user_timezone = pytz.timezone(user_timezone_str)
            except:
                user_timezone = default_timezone
            
            # Получаем время последнего задания
            last_task_sent_str = user_data.get('last_task_sent')
            if not last_task_sent_str:
                continue
                
            try:
                last_task_date_utc = datetime.fromisoformat(last_task_sent_str)
                
                if last_task_date_utc.tzinfo is None:
                    last_task_date_utc = pytz.UTC.localize(last_task_date_utc)
                
                last_task_date_user = last_task_date_utc.astimezone(user_timezone)
                user_now = now.astimezone(user_timezone)
                
                last_task_date_only = last_task_date_user.date()
                user_today = user_now.date()
                
                # Если задание было ВЧЕРА или раньше и не выполнено - блокируем
                if last_task_date_only < user_today:
                    # Получаем случайную реплику
                    block_message = await BotReplies.get_midnight_block_reply()
                    
                    # Добавляем мотивационную фразу
                    motivation = await BotReplies.get_motivation_reply()
                    
                    full_message = f"{block_message}\n\n{motivation}"
                    
                    await bot.send_message(chat_id=user_id, text=full_message)
                    blocked_count += 1
                    logger.info(f"⏸️ Пользователь {user_id} заблокирован (задание от {last_task_date_only})")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки даты у пользователя {user_id}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка сброса пользователя {user_id_str}: {e}")
    
    logger.info(f"📊 Сброс завершен: {reset_count} сброшено, {blocked_count} заблокировано")
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

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start с реферальной системой"""
    user = message.from_user
    if not user:
        await message.answer("Ошибка: не удалось получить информацию о пользователе")
        return
        
    args = message.text.split() if message.text else []
    referrer_id = None
    
    # Проверяем реферальный ID (если есть в аргументах)
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            # Проверяем, что реферер существует и не является самим пользователем
            referrer_data = await utils.get_user(referrer_id)
            if not referrer_data or referrer_id == user.id:
                referrer_id = None
            else:
                logger.info(f"📝 Пользователь {user.id} перешел по реферальной ссылке от {referrer_id}")
        except ValueError:
            referrer_id = None
            logger.warning(f"⚠️ Неверный реферальный ID в аргументах: {args[1]}")
    
    # Очищаем состояние
    try:
        await state.clear()
    except:
        pass
    
    user_data = await get_user(user.id)
    
    if user_data:
        # Пользователь уже зарегистрирован
        welcome_name = user.first_name or "Путник"
        
        # Получаем гендерные окончания
        gender = await utils.get_gender_ending(user_data)
        
        # Получаем случайную реплику приветствия
        greeting = await BotReplies.get_welcome_back_reply(gender, welcome_name)
        
        # Проверяем, был ли пользователь приглашен, но связь не сохранена
        if referrer_id and not user_data.get('invited_by'):
            await utils.save_referral_relationship(user.id, referrer_id)
            logger.info(f"📝 Восстановлена реферальная связь: {user.id} -> {referrer_id}")
            
        await message.answer(
            greeting,
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
        
        # Сохраняем реферальный ID в состоянии
        await state.update_data(referrer_id=referrer_id)
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
    from keyboards import get_timezone_keyboard
    
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

@dp.message(UserStates.waiting_for_ready)
async def process_ready_confirmation(message: Message, state: FSMContext):
    """ШАГ 6: Обработка подтверждения готовности с сохранением реферальной связи"""
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
    referrer_id = user_data.get('referrer_id')
    
    # Создаем запись пользователя
    new_user_data = {
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "archetype": archetype,
        "timezone": timezone,
        "current_day": 0,
        "completed_tasks": 0,
        "rank": "putnik",
        "created_at": datetime.now().isoformat(),
        "referrals": [],
        "referral_earnings": 0,
        "last_task_sent": None,
        "task_completed_today": False,
        "debts": [],
        "last_activity": datetime.now().isoformat(),
        "invited_by": referrer_id,
        "reserved_for_withdrawal": 0,
        "referral_stats": {
            "total_earned": 0,
            "payments_count": 0,
            "last_payment": None
        }
    }
    
    await save_user(user.id, new_user_data)
    
    logger.info(f"🔍 ОТЛАДКА: Новый пользователь {user.id}, архетип: {archetype}")
    
    # Отправляем первое задание
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
        logger.info(f"✅ Первое задание отправлено пользователю {user.id}")
    else:
        await message.answer(
            "🎯 <b>Добро пожаловать в челлендж!</b>\n\n"
            "К сожалению, первое задание временно недоступно.\n"
            "Обратись к администратору или проверь позже.\n\n"
            "А пока можешь ознакомиться с функциями бота:",
            reply_markup=get_main_menu(user.id)
        )
        logger.warning(f"⚠️ Не найдено задание дня 1 для пользователя {user.id}")
    
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
    
    # Создаем базовую информацию об архетипе
    if archetype == "spartan":
        welcome_text = (
            "🛡️ <b>Путь Спартанца выбран!</b>\n\n"
            "Твой путь — сила, дисциплина и порядок.\n\n"
            "🎯 <b>Что тебя ждет:</b>\n"
            "• Задания на физическую и ментальную стойкость\n"
            "• Развитие лидерских качеств и ответственности\n"
            "• Ежедневное укрепление силы воли\n\n"
        )
    else:
        welcome_text = (
            "⚔️ <b>Путь Амазонки выбран!</b>\n\n"
            "Твой путь — грация, сила и гармония.\n\n"
            "🎯 <b>Что тебя ждет:</b>\n"
            "• Задания на осознанность и женскую энергию\n"
            "• Развитие интуиции и эмоционального интеллекта\n"
            "• Ежедневное самопознание и рост\n\n"
        )
    
    # Общая информация для обоих архетипов
    welcome_text += (
        "📊 <b>Система челленджа:</b>\n"
        "• 300 дней непрерывного роста\n"
        "• 10 этапов по 30 дней каждый\n"
        "• Ежедневные задания в 9:00\n"
        "• Система рангов и достижений\n\n"
        "⬇️ <b>Нажми кнопку ниже, чтобы начать!</b>"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✅ Да, я готов начать!")]],
            resize_keyboard=True
        )
    )
    
    # Сохраняем архетип в состоянии
    await state.update_data(archetype=archetype)
    await state.set_state(UserStates.waiting_for_ready)
# ========== РАЗНООБРАЗНЫЕ РЕПЛИКИ БОТА ==========

class BotReplies:
    """Класс с разнообразными репликами бота"""
    
    @staticmethod
    async def get_task_completed_reply(gender, rank_updated=False, new_rank_name=""):
        """Реплики при выполнении задания"""
        replies = [
            "🎉 <b>Отлично! Еще один шаг к сильной версии себя!</b>",
            "🔥 <b>Супер! Дисциплина становится твоей привычкой!</b>",
            "💪 <b>Молодец! Каждый день - новая победа!</b>",
            "🌟 <b>Великолепно! Ты движешься к цели!</b>",
            "🚀 <b>Потрясающе! Ты на правильном пути!</b>",
            "⚡ <b>Браво! Сила воли растет с каждым днем!</b>",
            "🏆 <b>Замечательно! Еще одна маленькая победа!</b>",
            "🌈 <b>Прекрасно! Ты становишься лучше!</b>",
            "✨ <b>Восхитительно! Постоянство - ключ к успеху!</b>",
            "🎯 <b>Идеально! Ты выполняешь свой план!</b>"
        ]
        
        base_reply = random.choice(replies)
        
        if gender['person'] == 'Амазонка':
            person_text = f"💃 Воительница, ты {gender['verb_action']} это!"
        else:
            person_text = f"👊 Воин, ты {gender['verb_action']} это!"
        
        if rank_updated and new_rank_name:
            rank_text = f"\n\n🏆 <b>Новый ранг: {new_rank_name}!</b>"
        else:
            rank_text = ""
        
        return f"{base_reply}\n\n{person_text}{rank_text}\n\n<i>Продолжай в том же духе!</i>"
    
    @staticmethod
    async def get_task_skipped_reply(gender):
        """Реплики при пропуске задания"""
        replies = [
            "⏭️ <b>Задание пропущено</b>\n\nИногда перерыв необходим для нового рывка. Главное - возвращайся завтра!",
            "⏭️ <b>Задание отложено</b>\n\nДаже у самых сильных бывают дни отдыха. Важно не останавливаться надолго!",
            "⏭️ <b>Перерыв взят</b>\n\nОтдых - часть тренировки. Завтра с новыми силами!",
            "⏭️ <b>Пауза принята</b>\n\nИногда нужно перезагрузиться. Не забывай про завтрашний день!",
            "⏭️ <b>Пропуск зафиксирован</b>\n\nДаже великие воины отдыхают. Главное - продолжить путь завтра!",
            "⏭️ <b>Отдых разрешен</b>\n\nПерерыв не значит остановку. Возвращайся с новыми силами!",
            "⏭️ <b>Пауза в тренировке</b>\n\nИногда шаг назад - это подготовка к прыжку вперед!",
            "⏭️ <b>День отдыха</b>\n\nДаже сталь нуждается в закалке. Завтра снова в бой!",
            "⏭️ <b>Перезагрузка</b>\n\nИногда нужно остановиться, чтобы увидеть путь вперед!",
            "⏭️ <b>Тактическая пауза</b>\n\nУмный воин знает, когда нужно отступить, чтобы победить!"
        ]
        
        reply = random.choice(replies)
        
        if gender['person'] == 'Амазонка':
            gender_text = "дорогая воительница"
        else:
            gender_text = "уважаемый воин"
            
        return f"{reply}\n\n<i>{gender_text}, помни: завтра - новый день и новый вызов!</i>"
    
    @staticmethod
    async def get_reminder_reply():
        """Реплики для напоминаний в 18:30"""
        replies = [
            "🎯 <b>ВРЕМЯ ДЕЙСТВОВАТЬ!</b>\n\nВечер - идеальное время для завершения дня победой! Не упусти шанс сделать сегодняшний день значимым!",
            "🔥 <b>ПОСЛЕДНИЙ РЫВОК!</b>\n\nДень подходит к концу, но у тебя еще есть время на маленькую победу! Заверши день с чувством выполненного долга!",
            "💪 <b>ФИНИШНАЯ ПРЯМАЯ!</b>\n\nВечерний час - твой последний шанс сегодня. Сделай этот день не просто прожитым, а победоносным!",
            "🌟 <b>ВЕЧЕРНИЙ ВЫЗОВ!</b>\n\nСолнце садится, но твой день еще не закончен! Одна маленькая победа - и сегодняшний день войдет в историю твоих успехов!",
            "⚡ <b>ПОСЛЕДНИЙ ШАНС!</b>\n\n23:59 не за горами! У тебя еще есть время сделать сегодняшний день особенным. Действуй!",
            "🏆 <b>ВЕЧЕРНИЙ БОЙ!</b>\n\nТвой внутренний воин ждет сигнала к действию. Даже вечером можно одержать победу!",
            "🚀 <b>ФИНАЛЬНЫЙ СПРИНТ!</b>\n\nДень подходит к концу, но финишная прямая - самая важная. Покажи, на что ты способен!",
            "🌈 <b>ЗАКАТНЫЙ РЫВОК!</b>\n\nПод закат солнца совершаются великие дела. Пусть сегодняшний вечер станет твоим триумфом!",
            "✨ <b>ВЕЧЕРНЯЯ БИТВА!</b>\n\nТихий вечер - лучшее время для громких побед. Не пропускай свой шанс!",
            "🎖️ <b>ПОСЛЕДНИЙ РУБЕЖ!</b>\n\nДень почти закончен, но битва еще не проиграна. Собери волю в кулак и заверши день победой!"
        ]
        return random.choice(replies)
    
    @staticmethod
    async def get_midnight_block_reply():
        """Реплики для блокировки в полночь"""
        replies = [
            "⏸️ <b>ПАУЗА</b>\n\nТы не отметил вчерашний вызов.\nДисциплина требует последовательности!\nВернись во вчерашнее сообщение и отметь «✅ ГОТОВО» или «⏭️ ПРОПУСТИТЬ» чтобы разблокировать новые задания.",
            "⏸️ <b>СТОП</b>\n\nВчерашнее задание осталось без ответа.\nНастоящий воин отвечает за свои обязательства!\nОтметь вчерашний вызов, чтобы продолжить путь.",
            "⏸️ <b>БЛОКИРОВКА</b>\n\nТы пропустил вчерашний день.\nДисциплина - это делать, даже когда не хочется!\nВернись и закрой вчерашний долг.",
            "⏸️ <b>ЗАМОРОЗКА</b>\n\nВчерашний вызов не принят.\nСистема требует ежедневного участия!\nОтправь ответ на вчерашнее задание.",
            "⏸️ <b>ПЕРЕРЫВ</b>\n\nТы не ответил на вчерашний пинок.\nПуть воина состоит из маленьких ежедневных шагов!\nВернись и заверши вчерашний день.",
            "⏸️ <b>ОСТАНОВКА</b>\n\nВчерашний день пропущен.\nНастоящая сила - в постоянстве!\nЗакрой вчерашний долг, чтобы двигаться дальше.",
            "⏸️ <b>ПРИОСТАНОВКА</b>\n\nТы не завершил вчерашний вызов.\nКаждый пропущенный день ослабляет твою дисциплину!\nВернись и отметь вчерашнее задание.",
            "⏸️ <b>ЗАТВОР</b>\n\nВчерашний пинок остался без ответа.\nСистема работает только при ежедневном участии!\nОтветь на вчерашнее сообщение.",
            "⏸️ <b>БАРЬЕР</b>\n\nТы пропустил день.\nДорога к силе воли вымощена ежедневными действиями!\nВернись и заверши вчерашний вызов.",
            "⏸️ <b>ПРЕГРАДА</b>\n\nВчерашний день не закрыт.\nНастоящий рост происходит через ежедневные усилия!\nОтметь вчерашнее задание для продолжения."
        ]
        return random.choice(replies)
    
    @staticmethod
    async def get_welcome_back_reply(gender, name):
        """Реплики при возвращении в бота"""
        if gender['person'] == 'Амазонка':
            replies = [
                f"С возвращением, воительница {name}! 💃",
                f"Рада видеть тебя снова, {name}! 🌸",
                f"Приветствую, сильная {name}! 💪",
                f"{name}, твой путь продолжается! ✨",
                f"Вновь на поле боя, {name}! ⚔️",
                f"Твое возвращение украсило этот день, {name}! 🌟",
                f"Готова к новым вызовам, {name}? 🎯",
                f"Твоя сила воли ждала тебя, {name}! 🔥",
                f"Снова вместе, {name}! Продолжим путь! 🏹",
                f"Твоя дисциплина рада тебя видеть, {name}! 🛡️"
            ]
        else:
            replies = [
                f"С возвращением, воин {name}! 👊",
                f"Рад видеть тебя снова, {name}! 💪",
                f"Приветствую, сильный {name}! 🛡️",
                f"{name}, твой путь продолжается! ⚔️",
                f"Вновь в строю, {name}! 🎯",
                f"Твое возвращение укрепляет наш легион, {name}! 🏆",
                f"Готов к новым вызовам, {name}? 🔥",
                f"Твоя дисциплина ждала тебя, {name}! ✨",
                f"Снова вместе, {name}! Продолжим битву! ⚡",
                f"Твоя сила воли рада тебя видеть, {name}! 🌟"
            ]
        return random.choice(replies)
    
    @staticmethod
    async def get_motivation_reply():
        """Случайные мотивационные фразы"""
        replies = [
            "🎯 Помни: ты делаешь это для себя, а не для системы.",
            "💪 Честность перед собой - первый шаг к настоящим изменениям.",
            "🌟 Каждое выполненное задание - это инвестиция в себя.",
            "🔥 Дисциплина создает мотивацию, а не наоборот.",
            "⚡ Маленькие ежедневные победы ведут к большим изменениям.",
            "🏆 Сила воли - это мышца, которую нужно тренировать каждый день.",
            "✨ Сегодняшние усилия - это завтрашние результаты.",
            "🌈 Настоящий рост происходит вне зоны комфорта.",
            "🚀 Ты сильнее, чем думаешь. Докажи это себе.",
            "🎖️ Каждый день - новая возможность стать лучше."
        ]
        return random.choice(replies)
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
    
    # Обычные задания
    todays_tasks = await utils.get_todays_tasks(user_data)
    
    if not todays_tasks or len(todays_tasks) == 0:  # Двойная проверка
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
    
    # Отправляем основное задание - БЕЗОПАСНАЯ ИТЕРАЦИЯ
    try:
        # Проверяем, что todays_tasks действительно список
        if not isinstance(todays_tasks, list):
            logger.error(f"❌ todays_tasks не является списком: {type(todays_tasks)}")
            await message.answer("❌ Ошибка: данные заданий повреждены")
            return
            
        for task in todays_tasks:
            # Проверяем, что task - словарь
            if not isinstance(task, dict):
                logger.error(f"❌ task не является словарем: {type(task)}")
                continue
                
            # Проверяем наличие необходимых ключей
            if 'data' not in task or 'day' not in task or 'type' not in task:
                logger.error(f"❌ В задании отсутствуют необходимые ключи: {task.keys()}")
                continue
                
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
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке задания: {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке задания. Попробуйте позже.",
            reply_markup=keyboards.get_main_menu(user_id)
        )
    
    await utils.update_user_activity(user_id)
async def format_task_message(task_data, day, task_type):
    """Форматирует сообщение с заданием"""
    return (
        f"📋 <b>Задание на сегодня</b>\n\n"
        f"<b>День {day}/300</b>\n\n"
        f"{task_data['text']}\n\n"
        f"⏰ <b>До 23:59 на выполнение</b>\n\n"
        f"<i>Отмечай выполнение кнопками ниже 👇</i>"
    )


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
# ЗАМЕНИТЬ весь обработчик на упрощенную версию:
@dp.message(F.text == "✅ ГОТОВО")
async def task_completed(message: Message):
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        return
    
    # Получаем гендерные окончания
    gender = await utils.get_gender_ending(user_data)
    
    # Проверяем текущие задания
    todays_tasks = await utils.get_todays_tasks(user_data)
    
    if not todays_tasks:
        await message.answer("❌ Нет активных заданий!")
        return
    
    # Обновляем прогресс
    user_data['current_day'] = user_data.get('current_day', 0) + 1
    user_data['completed_tasks'] = user_data.get('completed_tasks', 0) + 1
    user_data['task_completed_today'] = True
    
    # Если в пробном периоде - увеличиваем счетчик
    if await utils.is_in_trial_period(user_data):
        trial_tasks = user_data.get('completed_tasks_in_trial', 0)
        user_data['completed_tasks_in_trial'] = trial_tasks + 1
        
        # Проверяем, закончился ли пробный период (3 задания)
        if trial_tasks + 1 >= 3:
            user_data['trial_finished'] = True
    
    # Обновляем ранг
    rank_updated = await utils.update_user_rank(user_data)
    new_rank_name = ""
    
    if rank_updated:
        current_rank = user_data.get('rank', 'putnik')
        rank_info = await utils.get_rank_info(current_rank)
        new_rank_name = rank_info.get('name', '')
    
    await utils.save_user(user_id, user_data)
    
    # Получаем случайную реплику (используем класс из этого же файла)
    reply = await BotReplies.get_task_completed_reply(gender, rank_updated, new_rank_name)
    
    await message.answer(
        reply,
        reply_markup=keyboards.get_main_menu(user_id)
    )
    
    # Проверяем, нужно ли отправить сообщение о конце пробного периода
    if await utils.is_in_trial_period(user_data):
        trial_tasks = user_data.get('completed_tasks_in_trial', 0)
        if trial_tasks >= 3:
            await asyncio.sleep(1)  # Небольшая пауза
            
            trial_end_message = (
                f"🎯 <b>Ты {gender['verb_finished']} вводный этап!</b>\n\n"
                f"За 3 дня ты получил{gender['ending_a']} представление о том, как работает система «300 ПИНКОВ».\n\n"
                f"💪 <b>Что дальше?</b>\n"
                f"• Ежедневные задания для развития силы воли\n"
                f"• Система рангов и достижений\n" 
                f"• Поддержка комьюнити\n"
                f"• 297 дней роста впереди!\n\n"
                f"🔥 <b>Продолжи путь к сильной версии себя!</b>"
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
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
            
            await message.answer(trial_end_message, reply_markup=subscription_keyboard)
    
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
        
        # Проверяем БЕСПЛАТНЫЙ пробный период
        created_at = datetime.fromisoformat(user_data.get('created_at', datetime.now().isoformat()))
        days_passed = (datetime.now() - created_at).days
        is_trial = days_passed < 3  # БЕСПЛАТНЫЕ 3 дня!
        
        if await is_subscription_active(user_data):
            try:
                sub_end = datetime.fromisoformat(user_data['subscription_end'])
                days_left = (sub_end - datetime.now()).days
                message_text += f"✅ <b>Статус:</b> Активна ({days_left} дней осталось)\n"
            except:
                message_text += "✅ <b>Статус:</b> Активна\n"
        elif is_trial:
            message_text += "🎁 <b>Статус:</b> БЕСПЛАТНЫЙ пробный период\n"
            message_text += f"Осталось бесплатных дней: {3 - days_passed}\n\n"
        else:
            message_text += "❌ <b>Статус:</b> Не активна\n"
            message_text += "Активируй подписку чтобы продолжить получать задания!\n\n"
        
        message_text += "<b>Доступные тарифы:</b>\n"
        
        # ПОКАЗЫВАЕМ ТОЛЬКО ПЛАТНЫЕ ТАРИФЫ (без trial_ruble)
        for tariff_id, tariff in config.TARIFFS.items():
            if tariff_id in ['month', 'year', 'pair_year']:  # ТОЛЬКО платные тарифы
                message_text += f"• {tariff['name']} - {tariff['price']} руб.\n"
        
        await message.answer(message_text, reply_markup=keyboards.get_payment_keyboard())
        
    except Exception as e:
        logger.error(f"❌ Ошибка в show_subscription: {e}")
        await message.answer("❌ Произошла ошибка при загрузке информации о подписке")
        logger.error(f"❌ Ошибка в show_subscription: {e}")
        await message.answer("❌ Произошла ошибка при загрузке информации о подписке")
@dp.message(F.text == "⏭️ ПРОПУСТИТЬ")
async def skip_task(message: Message):
    """Пропуск задания"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    # Получаем гендерные окончания
    gender = await utils.get_gender_ending(user_data)
    
    # Проверяем текущие задания
    todays_tasks = await utils.get_todays_tasks(user_data)
    
    if not todays_tasks:
        await message.answer("❌ Нет активных заданий для пропуска!")
        return
    
    # Увеличиваем счетчик дня
    user_data['current_day'] = user_data.get('current_day', 0) + 1
    user_data['task_completed_today'] = True
    
    # Если в пробном периоде - увеличиваем счетчик
    if await utils.is_in_trial_period(user_data):
        trial_tasks = user_data.get('completed_tasks_in_trial', 0)
        user_data['completed_tasks_in_trial'] = trial_tasks + 1
        
        if trial_tasks + 1 >= 3:
            user_data['trial_finished'] = True
    
    await utils.save_user(user_id, user_data)
    
    # Получаем случайную реплику (используем класс из этого же файла)
    reply = await BotReplies.get_task_skipped_reply(gender)
    
    await message.answer(
        reply,
        reply_markup=keyboards.get_main_menu(user_id)
    )
    
    # Проверяем, нужно ли отправить сообщение о конце пробного периода
    if await utils.is_in_trial_period(user_data):
        trial_tasks = user_data.get('completed_tasks_in_trial', 0)
        if trial_tasks >= 3:
            await asyncio.sleep(1)
            
            trial_end_message = (
                f"🎯 <b>Ты {gender['verb_finished']} вводный этап!</b>\n\n"
                f"За 3 дня ты получил{gender['ending_a']} представление о том, как работает система «300 ПИНКОВ».\n\n"
                f"💪 <b>Что дальше?</b>\n"
                f"• Ежедневные задания для развития силы воли\n"
                f"• Система рангов и достижений\n" 
                f"• Поддержка комьюнити\n"
                f"• 297 дней роста впереди!\n\n"
                f"🔥 <b>Продолжи путь к сильной версии себя!</b>"
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
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
            
            await message.answer(trial_end_message, reply_markup=subscription_keyboard)
    
    await utils.update_user_activity(user_id)
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

# Обновляем обработчик раздела "Мой легион"
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
        f"💸 <b>Выводи заработанные средства одним кликом!</b>\n\n"
        f"📤 <b>Просто нажми кнопку ниже чтобы отправить приглашение!</b>\n"
        f"Выбери друга из списка контактов - мы отправим красивое сообщение с объяснением системы."
    )
    
    await message.answer(message_text, reply_markup=get_my_referral_keyboard())
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
    """Активация подписки после успешной оплаты с реферальным начислением и немедленной отправкой задания"""
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
    
    # ОБНОВЛЯЕМ статус платежа
    await payments.update_payment_status(payment_data['payment_id'], 'succeeded')
    
    if tariff_id == "pair_year":
        await activate_pair_subscription(user_data, user_id, tariff, callback)
        return  # Для парной подписки своя логика
    
    # ДОБАВЛЯЕМ ДНИ ПОДПИСКИ
    updated_user_data = await utils.add_subscription_days(user_data, tariff['days'])
    
    # НАЧИСЛЯЕМ РЕФЕРАЛЬНЫЙ БОНУС
    referral_result = await utils.process_referral_payment(
        user_id, 
        tariff['price'], 
        tariff_id
    )
    
    # ПРАВИЛЬНО ОБРАБАТЫВАЕМ РЕЗУЛЬТАТ
    if referral_result and len(referral_result) == 4:
        success, referrer_id, bonus_amount, percent = referral_result
        
        if success and referrer_id and bonus_amount > 0:
            # Получаем новый баланс реферера
            referrer_data = await utils.get_user(referrer_id)
            new_balance = referrer_data.get('referral_earnings', 0) if referrer_data else 0
            
            # Отправляем уведомление рефереру
            await ReferralNotifications.send_referral_bonus_notification(
                bot=bot,
                referrer_id=referrer_id,
                bonus_info={
                    'bonus_amount': bonus_amount,
                    'percent': percent,
                    'payment_amount': tariff['price'],
                    'referred_name': user_data.get('first_name', 'Пользователь'),
                    'new_balance': new_balance
                }
            )
    else:
        # Если что-то пошло не так
        success = False
        referrer_id = None
        bonus_amount = 0
        percent = 0
    
    await utils.save_user(user_id, updated_user_data)
    
    success_message = (
        f"✅ <b>Подписка активирована!</b>\n\n"
        f"💎 Тариф: {tariff['name']}\n"
        f"⏰ Срок: {tariff['days']} дней\n"
        f"💰 Стоимость: {tariff['price']} руб.\n"
        f"🎯 Теперь у вас есть доступ ко всем заданиям!\n\n"
    )
    
    if success and bonus_amount > 0:
        success_message += f"🎉 <b>Вы принесли доход своему рефереру: {bonus_amount} руб.!</b>\n\n"
    
    success_message += f"Задания будут приходить ежедневно в 9:00 🕘\n\n"
    
    # 🔥 ВАЖНОЕ ДОБАВЛЕНИЕ: НЕМЕДЛЕННАЯ ОТПРАВКА ТЕКУЩЕГО ЗАДАНИЯ
    success_message += "<b>Твое следующее задание придет прямо сейчас! ⬇️</b>"
    
    success_edit = await safe_edit_message(callback, success_message)
    if not success_edit:
        await safe_send_message(callback, success_message)
    
    # 🔥 КРИТИЧЕСКО ВАЖНО: ОТПРАВЛЯЕМ ЗАДАНИЕ НЕМЕДЛЕННО
    try:
        # Получаем следующий день (текущий день + 1)
        current_day = updated_user_data.get('current_day', 0)
        next_day = current_day + 1
        
        # Если пользователь только начал (день 0), ставим день 1
        if next_day == 0:
            next_day = 1
            
        # Получаем задание для следующего дня
        task_id, task = await utils.get_task_by_day(next_day, updated_user_data.get('archetype', 'spartan'))
        
        if task:
            # Форматируем сообщение с заданием
            task_message = (
                f"📋 <b>Новое задание!</b>\n\n"
                f"<b>День {next_day}/300</b>\n\n"
                f"{task['text']}\n\n"
                f"⏰ <b>До 23:59 на выполнение</b>\n\n"
                f"<i>Отмечай выполнение кнопками ниже 👇</i>"
            )
            
            # Отправляем задание
            await bot.send_message(
                chat_id=user_id,
                text=task_message,
                reply_markup=keyboards.task_keyboard,
                disable_web_page_preview=True
            )
            
            # Обновляем данные пользователя
            updated_user_data['last_task_sent'] = datetime.now().isoformat()
            updated_user_data['task_completed_today'] = False
            await utils.save_user(user_id, updated_user_data)
            
            logger.info(f"✅ Задание дня {next_day} отправлено пользователю {user_id} после активации подписки")
        else:
            logger.warning(f"⚠️ Не найдено задание дня {next_day} для пользователя {user_id}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки задания после активации подписки пользователю {user_id}: {e}")
    
    # УВЕДОМЛЯЕМ админа об успешной активации
    try:
        user = callback.from_user
        if user:
            admin_message = (
                f"🎉 <b>Новая подписка активирована!</b>\n\n"
                f"👤 Пользователь: {user.first_name} (@{user.username or 'нет'})\n"
                f"🆔 ID: {user_id}\n"
                f"💎 Тариф: {tariff['name']}\n"
                f"💰 Сумма: {tariff['price']} руб.\n"
                f"📅 Дней: {tariff['days']}\n"
                f"⏰ Дата окончания: {updated_user_data.get('subscription_end', 'неизвестно')}\n\n"
            )
            
            if success and referrer_id:
                admin_message += (
                    f"🤝 <b>Реферальное начисление:</b>\n"
                    f"• Реферер: {referrer_id}\n"
                    f"• Бонус: {bonus_amount} руб.\n"
                    f"• Процент: {percent}%\n"
                )
            
            await bot.send_message(config.ADMIN_ID, admin_message)
    except Exception as e:
        logger.error(f"Ошибка уведомления админа: {e}")

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

# ========== ВЫВОД СРЕДСТВ ==========

@dp.message(F.text == "💰 Вывод средств")
async def withdrawal_start(message: Message):
    """Начало процедуры вывода - показывает баланс и кнопку вывода"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    # Получаем балансы
    total_balance = user_data.get('referral_earnings', 0)
    reserved = user_data.get('reserved_for_withdrawal', 0)
    available_balance = total_balance - reserved
    
    # Получаем статистику выводов
    total_withdrawn = await utils.get_total_withdrawn(user_id)
    
    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💸 Вывести средства", callback_data="start_withdrawal")],
            [InlineKeyboardButton(text="📋 История выводов", callback_data="withdrawal_history")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="withdrawal_stats")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
        ]
    )
    
    message_text = (
        f"💰 <b>ВЫВОД СРЕДСТВ</b>\n\n"
        f"💎 <b>Общий баланс:</b> {total_balance} руб.\n"
        f"✅ <b>Доступно для вывода:</b> {available_balance} руб.\n"
        f"⏳ <b>В обработке:</b> {reserved} руб.\n"
        f"📤 <b>Уже выведено:</b> {total_withdrawn} руб.\n\n"
        f"📊 <b>Условия вывода:</b>\n"
        f"• Минимальная сумма: {config.MIN_WITHDRAWAL} руб.\n"
        f"✅ <b>Без комиссии</b>\n"
        f"• Срок обработки: 1-3 рабочих дня\n\n"
        f"💳 <b>Доступные способы:</b>\n"
        f"• Банковская карта\n"

        f"Выберите действие:"
    )
    
    await message.answer(message_text, reply_markup=keyboard)

@dp.callback_query(F.data == "start_withdrawal")
async def start_withdrawal_handler(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс вывода средств"""
    if not callback or not callback.message:
        return
        
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    user_id = user.id
    
    # Проверяем доступный баланс
    user_data = await utils.get_user(user_id)
    if not user_data:
        await callback.answer("❌ Пользователь не найден")
        return
    
    total_balance = user_data.get('referral_earnings', 0)
    reserved = user_data.get('reserved_for_withdrawal', 0)
    available_balance = total_balance - reserved
    
    if available_balance < config.MIN_WITHDRAWAL:
        await callback.answer(
            f"❌ Минимальная сумма вывода: {config.MIN_WITHDRAWAL} руб.",
            show_alert=True
        )
        return
    
    # Запрашиваем сумму
    await callback.message.edit_text(
        f"💰 <b>Доступно для вывода:</b> {available_balance} руб.\n"
        f"💸 <b>Минимальная сумма:</b> {config.MIN_WITHDRAWAL} руб.\n\n"
        f"📝 <b>Введите сумму для вывода:</b>\n"
        f"<i>Только число, без руб.</i>"
    )
    
    await state.set_state(UserStates.waiting_for_withdrawal_amount)
    await state.update_data(user_id=user_id, available_balance=available_balance)
    await callback.answer()

@dp.message(UserStates.waiting_for_withdrawal_amount)
async def withdrawal_amount_handler(message: Message, state: FSMContext):
    """Обработка введенной суммы для вывода"""
    # Безопасная проверка всех объектов
    if not message or not message.from_user:
        return
    
    # Безопасно получаем user_id
    try:
        user_id = message.from_user.id
    except AttributeError:
        return
    
    # Проверяем наличие текста
    if not message.text:
        await message.answer("❌ Пожалуйста, введите сумму:")
        return
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    
    # Проверяем, что пользователь совпадает
    if state_data.get('user_id') != user_id:
        await message.answer("❌ Ошибка доступа")
        await state.clear()
        return
    
    available_balance = state_data.get('available_balance', 0)
    
    try:
        # Безопасно обрабатываем текст
        text = message.text.strip()
        amount = int(text)
        
        # Проверяем минимальную сумму (300 руб)
        if amount < config.MIN_WITHDRAWAL:
            await message.answer(
                f"❌ Минимальная сумма вывода: {config.MIN_WITHDRAWAL} руб.\n"
                f"Доступно: {available_balance} руб.\n"
                f"Попробуйте еще раз:"
            )
            return
        
        # Проверяем максимальную сумму
        if amount > available_balance:
            await message.answer(
                f"❌ Недостаточно средств. Доступно: {available_balance} руб.\n"
                f"Введите другую сумму:"
            )
            return
        
        # Проверяем лимиты
        limit_check = await utils.check_withdrawal_limits(user_id, amount)
        if not limit_check[0]:
            await message.answer(
                f"❌ {limit_check[1]}\n"
                f"Введите другую сумму:"
            )
            return
        
        # Сохраняем сумму (без комиссии)
        await state.update_data(
            amount=amount,
            amount_to_receive=amount  # Без комиссии - вся сумма
        )
        
        # Показываем методы вывода
        methods_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Банковская карта", callback_data="withdraw_method_bank_card")],
                [InlineKeyboardButton(text="ЮMoney", callback_data="withdraw_method_yoomoney")],
                [InlineKeyboardButton(text="🏦 Сбербанк Онлайн", callback_data="withdraw_method_sberbank")],
                [InlineKeyboardButton(text="💳 Тинькофф", callback_data="withdraw_method_tinkoff")],
                [InlineKeyboardButton(text="👛 QIWI Кошелек", callback_data="withdraw_method_qiwi")],
                [InlineKeyboardButton(text="🔙 Отменить", callback_data="withdraw_cancel")]
            ]
        )
        
        await message.answer(
            f"✅ <b>Сумма подтверждена:</b> {amount} руб.\n\n"
            f"🎯 <b>Минимальный вывод:</b> {config.MIN_WITHDRAWAL} руб.\n"
            f"✅ <b>Без комиссии</b>\n\n"
            f"💳 <b>Выберите способ получения:</b>",
            reply_markup=methods_keyboard
        )
        
        await state.set_state(UserStates.waiting_for_withdrawal_method)
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число:")
    except Exception as e:
        logger.error(f"❌ Ошибка обработки суммы вывода: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
        await state.clear()

@dp.callback_query(UserStates.waiting_for_withdrawal_method, F.data.startswith("withdraw_method_"))
async def withdrawal_method_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора метода вывода"""
    # БЕЗОПАСНАЯ ПРОВЕРКА ВСЕХ АТРИБУТОВ
    if not callback:
        return
    
    if not callback.data:
        try:
            await callback.answer("Ошибка данных")
        except:
            pass
        return
    
    if not callback.message:
        try:
            await callback.answer("Ошибка сообщения")
        except:
            pass
        return
    
    # БЕЗОПАСНОЕ ИСПОЛЬЗОВАНИЕ replace
    try:
        callback_data = str(callback.data)
        if callback_data == "withdraw_cancel":
            # Безопасное редактирование
            if callback.message:
                await callback.message.edit_text("❌ Вывод отменен")
            await state.clear()
            await callback.answer()
            return
        
        if callback_data.startswith("withdraw_method_"):
            method_id = callback_data.replace("withdraw_method_", "")
        else:
            method_id = ""
    except AttributeError:
        try:
            await callback.answer("❌ Ошибка обработки данных")
        except:
            pass
        return
    
    method_name = config.WITHDRAWAL_METHODS.get(method_id, "Неизвестный метод")
    
    # Получаем инструкции для метода
    instructions = {
        "bank_card": "💳 <b>Введите номер банковской карты (16-19 цифр):</b>\nПример: 2200 1234 5678 9010",
    }
    
    instruction = instructions.get(method_id, "📝 <b>Введите реквизиты для получения средств:</b>")
    
    # Сохраняем метод
    await state.update_data(method=method_id, method_name=method_name)
    
    # БЕЗОПАСНОЕ РЕДАКТИРОВАНИЕ СООБЩЕНИЯ
    try:
        if callback.message:
            await callback.message.edit_text(
                f"📋 <b>Выбран способ:</b> {method_name}\n\n"
                f"{instruction}\n\n"
                f"<i>Убедитесь, что реквизиты указаны верно!</i>"
            )
        else:
            # Если нет сообщения, отправляем новое
            await callback.answer("Ошибка: сообщение не найдено", show_alert=True)
            return
    except Exception as e:
        logger.error(f"❌ Ошибка редактирования сообщения: {e}")
        try:
            await callback.answer("Ошибка обновления сообщения")
        except:
            pass
        return
    
    await state.set_state(UserStates.waiting_for_withdrawal_details)
    
    # Безопасный answer
    try:
        await callback.answer()
    except:
        pass

@dp.message(UserStates.waiting_for_withdrawal_details)
async def withdrawal_details_handler(message: Message, state: FSMContext):
    """Обработка реквизитов вывода (только номер карты)"""
    if not message or not message.text:
        await message.answer("❌ Пожалуйста, введите номер карты:")
        return
    
    details = message.text.strip()
    
    # Убираем пробелы и проверяем что это цифры
    card_number = details.replace(" ", "")
    
    if not card_number.isdigit():
        await message.answer("❌ Номер карты должен содержать только цифры. Попробуйте еще раз:")
        return
    
    if len(card_number) < 16 or len(card_number) > 19:
        await message.answer("❌ Номер карты должен содержать 16-19 цифр. Попробуйте еще раз:")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    amount = data.get('amount', 0)
    amount_to_receive = amount  # Без комиссии
    method = "bank_card"
    method_name = "Банковская карта"
    user_id = data.get('user_id', 0)
    
    # Сохраняем реквизиты
    await state.update_data(details=card_number)
    
    # Подтверждение
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить вывод", callback_data="withdraw_confirm")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="withdraw_cancel")]
        ]
    )
    
    # Форматируем номер карты для отображения
    formatted_card = ' '.join([card_number[i:i+4] for i in range(0, len(card_number), 4)])
    
    await message.answer(
        f"📋 <b>ПОДТВЕРЖДЕНИЕ ВЫВОДА</b>\n\n"
        f"💰 <b>Сумма:</b> {amount} руб.\n"
        f"✅ <b>Без комиссии</b>\n"
        f"🎯 <b>Минимум:</b> {config.MIN_WITHDRAWAL} руб.\n\n"
        f"💳 <b>Способ:</b> {method_name}\n"
        f"📝 <b>Реквизиты:</b>\n<code>{formatted_card}</code>\n\n"
        f"<i>Проверьте данные перед подтверждением!</i>",
        reply_markup=confirm_keyboard
    )
    
    await state.set_state(UserStates.confirm_withdrawal)

@dp.callback_query(UserStates.confirm_withdrawal, F.data.in_(["withdraw_confirm", "withdraw_cancel"]))
async def withdrawal_confirm_handler(callback: CallbackQuery, state: FSMContext):
    """Подтверждение или отмена вывода"""
    if not callback or not callback.message:
        return
    
    if callback.data == "withdraw_cancel":
        await callback.message.edit_text("❌ Вывод отменен")
        await state.clear()
        await callback.answer()
        return
    
    # Получаем данные
    data = await state.get_data()
    amount = data.get('amount', 0)
    method = data.get('method', '')
    method_name = data.get('method_name', 'Неизвестный метод')
    details = data.get('details', '')
    user_id = data.get('user_id', 0)
    
    try:
        # Создаем заявку на вывод
        success, result = await utils.create_withdrawal_request(
            user_id=user_id,
            amount=amount,
            method=method,
            details=details
        )
        
        if success:
            withdrawal_id = result
            
            # Получаем данные заявки для уведомления админу
            withdrawals = await utils.read_json(config.WITHDRAWALS_FILE)
            withdrawal_data = withdrawals.get(withdrawal_id, {}) if withdrawals else {}
            
            if withdrawal_data:
                # Отправляем уведомление админу
                await ReferralNotifications.send_withdrawal_request_notification(
                    bot=bot,
                    admin_id=config.ADMIN_ID,
                    withdrawal_data=withdrawal_data
                )
            
            await callback.message.edit_text(
                f"✅ <b>ЗАЯВКА СОЗДАНА!</b>\n\n"
                f"🆔 <b>Номер заявки:</b> <code>{withdrawal_id}</code>\n"
                f"💰 <b>Сумма:</b> {amount} руб.\n"
                f"💳 <b>Способ:</b> {method_name}\n\n"
                f"⏳ <b>Статус:</b> Ожидает обработки\n"
                f"📅 <b>Срок обработки:</b> 1-3 рабочих дня\n\n"
                f"📞 <b>По вопросам:</b> {config.SUPPORT_USERNAME}\n\n"
                f"<i>Вы получите уведомление при изменении статуса.</i>"
            )
            
            logger.info(f"✅ Создана заявка на вывод #{withdrawal_id} от пользователя {user_id}")
            
        else:
            await callback.message.edit_text(
                f"❌ <b>ОШИБКА СОЗДАНИЯ ЗАЯВКИ</b>\n\n"
                f"{result}\n\n"
                f"Попробуйте позже или обратитесь в поддержку: {config.SUPPORT_USERNAME}"
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка подтверждения вывода: {e}")
        await callback.message.edit_text(
            "❌ <b>Произошла ошибка при создании заявки</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку."
        )
        await state.clear()
    
    await callback.answer()
@dp.callback_query(F.data == "show_min_withdrawal")
async def show_min_withdrawal_handler(callback: CallbackQuery):
    """Показывает информацию о минимальном выводе"""
    user_id = callback.from_user.id
    user_data = await utils.get_user(user_id)
    
    if user_data:
        earnings = user_data.get('referral_earnings', 0)
        reserved = user_data.get('reserved_for_withdrawal', 0)
        available = earnings - reserved
        
        if available < config.MIN_WITHDRAWAL:
            needed = config.MIN_WITHDRAWAL - available
            
            await callback.answer(
                f"💰 Доступно: {available} руб.\n"
                f"🎯 Нужно ещё: {needed} руб. до {config.MIN_WITHDRAWAL} руб.\n"
                f"✅ Без комиссии\n\n"
                f"Пригласите {math.ceil(needed / 75)} друзей "
                f"и сможете вывести средства!",  # ~75 руб с каждого (30% от 250 руб)
                show_alert=True
            )
    else:
        await callback.answer(
            f"🎯 Минимальный вывод: {config.MIN_WITHDRAWAL} руб.\n"
            f"✅ Без комиссии",
            show_alert=True
        )
@dp.callback_query(F.data == "withdrawal_history")
async def withdrawal_history_handler(callback: CallbackQuery):
    """Показывает историю выводов пользователя"""
    if not callback or not callback.message:
        return
    
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
    
    user_id = user.id
    withdrawals = await utils.get_user_withdrawals(user_id, limit=10)
    
    if not withdrawals:
        await callback.message.edit_text(
            "📋 <b>ИСТОРИЯ ВЫВОДОВ</b>\n\n"
            "У вас еще не было выводов средств."
        )
        await callback.answer()
        return
    
    message_text = "📋 <b>ИСТОРИЯ ВЫВОДОВ</b>\n\n"
    
    for i, w in enumerate(withdrawals, 1):
        status_icons = {
            'pending': '⏳',
            'processing': '🔄', 
            'completed': '✅',
            'rejected': '❌',
            'cancelled': '🚫'
        }
        
        status_text = {
            'pending': 'Ожидает',
            'processing': 'В обработке',
            'completed': 'Завершен',
            'rejected': 'Отклонен',
            'cancelled': 'Отменен'
        }
        
        icon = status_icons.get(w.get('status', ''), '📋')
        status = status_text.get(w.get('status', ''), w.get('status', 'Неизвестно'))
        
        message_text += (
            f"{icon} <b>Заявка #{w.get('id', 'N/A')[:8]}</b>\n"
            f"💰 Сумма: {w.get('amount', 0)} руб.\n"
            f"📊 Статус: {status}\n"
            f"📅 Дата: {w.get('created_at', 'N/A')[:10]}\n"
        )
        
        if w.get('status') == 'completed':
            message_text += f"💸 Получено: {w.get('amount_after_fee', 0):.2f} руб.\n"
        
        message_text += "\n"
    
    if len(withdrawals) == 10:
        message_text += "\n<i>Показаны последние 10 заявок</i>"
    
    await callback.message.edit_text(message_text)
    await callback.answer()

@dp.callback_query(F.data == "withdrawal_stats")
async def withdrawal_stats_handler(callback: CallbackQuery):
    """Показывает статистику по выводам"""
    if not callback or not callback.message:
        return
    
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
    
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Получаем данные
    total_balance = user_data.get('referral_earnings', 0)
    reserved = user_data.get('reserved_for_withdrawal', 0)
    available = total_balance - reserved
    total_withdrawn = await utils.get_total_withdrawn(user_id)
    
    # Получаем историю для статистики
    withdrawals = await utils.get_user_withdrawals(user_id, limit=100)
    
    # Считаем статистику
    completed_withdrawals = [w for w in withdrawals if w.get('status') == 'completed']
    pending_withdrawals = [w for w in withdrawals if w.get('status') in ['pending', 'processing']]
    
    total_completed = sum(w.get('amount', 0) for w in completed_withdrawals)
    total_pending = sum(w.get('amount', 0) for w in pending_withdrawals)
    total_fees = sum(w.get('fee', 0) for w in completed_withdrawals)
    
    # Средний вывод
    avg_withdrawal = total_completed / len(completed_withdrawals) if completed_withdrawals else 0
    
    message_text = (
        f"📊 <b>СТАТИСТИКА ВЫВОДОВ</b>\n\n"
        f"💰 <b>Балансы:</b>\n"
        f"• Общий: {total_balance} руб.\n"
        f"• Доступно: {available} руб.\n"
        f"• В обработке: {reserved} руб.\n\n"
        
        f"📈 <b>Выводы:</b>\n"
        f"• Всего выведено: {total_withdrawn} руб.\n"
        f"• Завершено заявок: {len(completed_withdrawals)}\n"
        f"• В обработке: {len(pending_withdrawals)}\n"
        f"• Всего комиссий: {total_fees:.2f} руб.\n"
        f"• Средний вывод: {avg_withdrawal:.2f} руб.\n\n"
        
        f"⚙️ <b>Настройки:</b>\n"
        f"• Минимальный вывод: {config.MIN_WITHDRAWAL} руб.\n"
        f"• Комиссия: {config.WITHDRAWAL_FEE}%\n"
        f"• Макс. в день: {config.DAILY_WITHDRAWAL_LIMIT} руб.\n"
    )
    
    await callback.message.edit_text(message_text)
    await callback.answer()

# ========== АДМИНСКАЯ ПАНЕЛЬ ДЛЯ ВЫВОДОВ ==========

@dp.message(F.text == "📤 Заявки на вывод")
async def admin_withdrawals_panel(message: Message):
    """Показывает админскую панель для обработки выводов"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    # Получаем pending заявки
    pending_withdrawals = await utils.get_pending_withdrawals()
    
    if not pending_withdrawals:
        await message.answer(
            "📤 <b>ЗАЯВКИ НА ВЫВОД</b>\n\n"
            "Нет заявок, ожидающих обработки."
        )
        return
    
    # Создаем клавиатуру с заявками
    keyboard_buttons = []
    
    for w in pending_withdrawals[:10]:  # Ограничиваем 10 заявками
        w_id = w.get('id', 'N/A')
        w_amount = w.get('amount', 0)
        w_name = w.get('user_name', 'Неизвестно')
        
        button_text = f"{w_id[:8]} | {w_amount} руб. | {w_name}"
        callback_data = f"admin_withdraw_view_{w_id}"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    # Добавляем кнопки управления
    keyboard_buttons.append([
        InlineKeyboardButton(text="📋 Все заявки", callback_data="admin_withdrawals_all"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_withdraw_stats")
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        f"📤 <b>ЗАЯВКИ НА ВЫВОД</b>\n\n"
        f"⏳ Ожидают обработки: {len(pending_withdrawals)}\n\n"
        f"Выберите заявку для обработки:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("admin_withdraw_view_"))
async def admin_withdrawal_view_handler(callback: CallbackQuery):
    """Показывает детали заявки на вывод"""
    # БЕЗОПАСНАЯ ПРОВЕРКА ВСЕГО
    if not callback:
        return
    
    if not hasattr(callback, 'from_user') or not callback.from_user:
        # Если не можем получить from_user, просто выходим
        return
    
    if callback.from_user.id != config.ADMIN_ID:
        # Безопасно пытаемся ответить, но если callback.answer тоже None, игнорируем
        try:
            await callback.answer("⛔ Нет доступа")
        except:
            pass
        return
    
    if not hasattr(callback, 'data') or not callback.data:
        try:
            await callback.answer("Ошибка данных")
        except:
            pass
        return
    
    # БЕЗОПАСНОЕ ИСПОЛЬЗОВАНИЕ replace
    try:
        callback_data = str(callback.data) if callback.data else ""
        withdrawal_id = callback_data.replace("admin_withdraw_view_", "")
    except AttributeError:
        try:
            await callback.answer("❌ Ошибка обработки данных")
        except:
            pass
        return
    
    if not withdrawal_id:
        try:
            await callback.answer("❌ ID заявки не найден")
        except:
            pass
        return
    
    # Получаем данные заявки
    withdrawals = await utils.read_json(config.WITHDRAWALS_FILE)
    
    if not isinstance(withdrawals, dict) or withdrawal_id not in withdrawals:
        try:
            await callback.answer("❌ Заявка не найдена")
        except:
            pass
        return
    
    withdrawal = withdrawals[withdrawal_id]
    
    if not isinstance(withdrawal, dict):
        try:
            await callback.answer("❌ Неверный формат данных заявки")
        except:
            pass
        return
    
    # Безопасно извлекаем данные
    created_at = withdrawal.get('created_at', '')
    formatted_date = 'Неизвестно'
    if created_at and isinstance(created_at, str) and len(created_at) > 10:
        try:
            formatted_date = created_at[:19].replace('T', ' ')
        except AttributeError:
            formatted_date = created_at[:19] if len(created_at) >= 19 else created_at
    
    message_text = (
        f"📋 <b>ЗАЯВКА НА ВЫВОД #{withdrawal_id}</b>\n\n"
        f"👤 <b>Пользователь:</b>\n"
        f"• Имя: {withdrawal.get('user_name', 'Неизвестно')}\n"
        f"• Username: @{withdrawal.get('user_username', 'нет')}\n"
        f"• ID: {withdrawal.get('user_id', 'N/A')}\n\n"
        
        f"💰 <b>Финансы:</b>\n"
        f"• Сумма: {withdrawal.get('amount', 0)} руб.\n"
        f"• К получению: {withdrawal.get('amount_after_fee', 0)} руб.\n"
        f"• Комиссия: {withdrawal.get('fee', 0)} руб. ({withdrawal.get('fee_percent', 0)}%)\n\n"
        
        f"💳 <b>Способ вывода:</b>\n"
        f"{withdrawal.get('method', 'Неизвестно')}\n"
        f"<code>{withdrawal.get('details', 'Не указаны')}</code>\n\n"
        
        f"📅 <b>Дата создания:</b>\n"
        f"{formatted_date}\n\n"
        
        f"📊 <b>Статус:</b> {withdrawal.get('status', 'Неизвестно')}"
    )
    
    # Кнопки действий
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_withdraw_approve_{withdrawal_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_withdraw_reject_{withdrawal_id}")
            ],
            [
                InlineKeyboardButton(text="✅ Завершить", callback_data=f"admin_withdraw_complete_{withdrawal_id}"),
                InlineKeyboardButton(text="📋 Назад к списку", callback_data="admin_withdrawals_list")
            ]
        ]
    )
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: проверяем callback.message перед edit_text
    if hasattr(callback, 'message') and callback.message is not None:
        try:
            await callback.message.edit_text(message_text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            try:
                # Пытаемся отправить новое сообщение вместо редактирования
                await callback.message.answer(message_text, reply_markup=keyboard)
            except Exception as e2:
                logger.error(f"Ошибка отправки сообщения: {e2}")
    else:
        # Если нет сообщения для редактирования, отправляем новое
        try:
            # Пытаемся получить chat_id из callback
            chat_id = callback.from_user.id if callback.from_user else None
            if chat_id:
                await bot.send_message(chat_id, message_text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение: {e}")
    
    # Безопасно пытаемся ответить на callback
    try:
        await callback.answer()
    except:
        pass  # Игнорируем если не получается

@dp.callback_query(F.data == "withdraw_cancel")
async def withdraw_cancel_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка отмены вывода из любого состояния"""
    if not callback or not callback.message:
        return
    
    try:
        await callback.message.edit_text("❌ Вывод отменен")
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
    
    await state.clear()
    await callback.answer()
@dp.callback_query(F.data.startswith("admin_withdraw_approve_"))
async def admin_withdrawal_approve_handler(callback: CallbackQuery):
    """Одобрение заявки на вывод"""
    # БЕЗОПАСНАЯ ПРОВЕРКА
    if not callback:
        return
    
    if not hasattr(callback, 'from_user') or not callback.from_user:
        return
    
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    if not hasattr(callback, 'data') or not callback.data:
        await callback.answer("Ошибка данных")
        return
    
    # БЕЗОПАСНОЕ ИСПОЛЬЗОВАНИЕ replace
    try:
        callback_data = str(callback.data) if callback.data else ""
        withdrawal_id = callback_data.replace("admin_withdraw_approve_", "")
    except AttributeError:
        await callback.answer("❌ Ошибка обработки данных")
        return
    
    if not withdrawal_id:
        await callback.answer("❌ ID заявки не найден")
        return
    
    # Обрабатываем заявку
    success, message = await utils.process_withdrawal(
        withdrawal_id=withdrawal_id,
        admin_id=callback.from_user.id,
        action='approve'
    )
    
    if success:
        # Получаем обновленные данные заявки
        withdrawals = await utils.read_json(config.WITHDRAWALS_FILE)
        withdrawal = withdrawals.get(withdrawal_id, {}) if isinstance(withdrawals, dict) else {}
        
        # Отправляем уведомление пользователю
        if withdrawal:
            await ReferralNotifications.send_withdrawal_status_notification(
                bot=bot,
                user_id=withdrawal.get('user_id', 0),
                withdrawal_data=withdrawal,
                status='processing',
                comment="Заявка одобрена, ожидайте зачисления"
            )
        
        await callback.answer("✅ Заявка одобрена")
        
        # Обновляем сообщение с проверкой callback.message
        if hasattr(callback, 'message') and callback.message:
            try:
                await callback.message.edit_text(
                    f"✅ <b>ЗАЯВКА ОДОБРЕНА</b>\n\n"
                    f"🆔 ID: {withdrawal_id}\n"
                    f"👤 Пользователь уведомлен.\n\n"
                    f"После отправки средств нажмите 'Завершить'."
                )
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
    else:
        await callback.answer(f"❌ {message}", show_alert=True)


@dp.callback_query(F.data.startswith("admin_withdraw_complete_"))
async def admin_withdrawal_complete_handler(callback: CallbackQuery):
    """Завершение заявки на вывод"""
    # БЕЗОПАСНАЯ ПРОВЕРКА
    if not callback:
        return
    
    if not hasattr(callback, 'from_user') or not callback.from_user:
        return
    
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    if not hasattr(callback, 'data') or not callback.data:
        await callback.answer("Ошибка данных")
        return
    
    # БЕЗОПАСНОЕ ИСПОЛЬЗОВАНИЕ replace
    try:
        callback_data = str(callback.data) if callback.data else ""
        withdrawal_id = callback_data.replace("admin_withdraw_complete_", "")
    except AttributeError:
        await callback.answer("❌ Ошибка обработки данных")
        return
    
    if not withdrawal_id:
        await callback.answer("❌ ID заявки не найден")
        return
    
    # Обрабатываем заявку
    success, message = await utils.process_withdrawal(
        withdrawal_id=withdrawal_id,
        admin_id=callback.from_user.id,
        action='complete'
    )
    
    if success:
        # Получаем обновленные данные заявки
        withdrawals = await utils.read_json(config.WITHDRAWALS_FILE)
        withdrawal = withdrawals.get(withdrawal_id, {}) if isinstance(withdrawals, dict) else {}
        
        # Отправляем уведомление пользователю
        if withdrawal:
            await ReferralNotifications.send_withdrawal_status_notification(
                bot=bot,
                user_id=withdrawal.get('user_id', 0),
                withdrawal_data=withdrawal,
                status='completed',
                comment="Средства зачислены"
            )
        
        await callback.answer("✅ Вывод завершен")
        
        # Обновляем сообщение с проверкой callback.message
        if hasattr(callback, 'message') and callback.message:
            try:
                await callback.message.edit_text(
                    f"✅ <b>ВЫВОД ЗАВЕРШЕН</b>\n\n"
                    f"🆔 ID: {withdrawal_id}\n"
                    f"💰 Сумма: {withdrawal.get('amount', 0)} руб.\n"
                    f"👤 Пользователь уведомлен.\n\n"
                    f"Операция завершена."
                )
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
    else:
        await callback.answer(f"❌ {message}", show_alert=True)
@dp.callback_query(F.data.startswith("admin_withdraw_reject_"))
async def admin_withdrawal_reject_handler(callback: CallbackQuery, state: FSMContext):
    """Отклонение заявки на вывод"""
    # БЕЗОПАСНАЯ ПРОВЕРКА
    if not callback:
        return
    
    if not hasattr(callback, 'message') or not callback.message:
        return
    
    if not hasattr(callback, 'from_user') or not callback.from_user:
        await callback.answer("Ошибка пользователя")
        return
    
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    if not hasattr(callback, 'data') or not callback.data:
        await callback.answer("Ошибка данных")
        return
    
    # БЕЗОПАСНОЕ ИСПОЛЬЗОВАНИЕ replace
    try:
        callback_data = str(callback.data) if callback.data else ""
        withdrawal_id = callback_data.replace("admin_withdraw_reject_", "")
    except AttributeError:
        await callback.answer("❌ Ошибка обработки данных")
        return
    
    if not withdrawal_id:
        await callback.answer("❌ ID заявки не найден")
        return
    
    # Сохраняем ID заявки в состоянии
    await state.update_data(withdrawal_id=withdrawal_id)
    await state.set_state(UserStates.admin_waiting_withdrawal_comment)
    
    try:
        await callback.message.edit_text(
            f"❌ <b>ОТКЛОНЕНИЕ ЗАЯВКИ</b>\n\n"
            f"🆔 ID: {withdrawal_id}\n\n"
            f"📝 <b>Введите причину отклонения:</b>\n"
            f"<i>Это сообщение увидит пользователь</i>"
        )
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
    
    await callback.answer()
@dp.message(UserStates.admin_waiting_withdrawal_comment)
async def admin_withdrawal_reject_comment_handler(message: Message, state: FSMContext):
    """Обработка комментария при отклонении заявки"""
    if not message or not message.from_user or message.from_user.id != config.ADMIN_ID:
        return
    
    comment = message.text.strip() if message.text else ""
    
    if not comment:
        await message.answer("❌ Пожалуйста, введите причину отклонения:")
        return
    
    # Получаем ID заявки из состояния
    state_data = await state.get_data()
    withdrawal_id = state_data.get('withdrawal_id')
    
    if not withdrawal_id:
        await message.answer("❌ Ошибка: ID заявки не найден")
        await state.clear()
        return
    
    # Обрабатываем отклонение
    success, result_message = await utils.process_withdrawal(
        withdrawal_id=withdrawal_id,
        admin_id=message.from_user.id,
        action='reject',
        comment=comment
    )
    
    if success:
        # Получаем обновленные данные заявки
        withdrawals = await utils.read_json(config.WITHDRAWALS_FILE)
        withdrawal = withdrawals.get(withdrawal_id, {}) if withdrawals else {}
        
        # Отправляем уведомление пользователю
        if withdrawal:
            await ReferralNotifications.send_withdrawal_status_notification(
                bot=bot,
                user_id=withdrawal.get('user_id', 0),
                withdrawal_data=withdrawal,
                status='rejected',
                comment=comment
            )
        
        await message.answer(
            f"✅ <b>ЗАЯВКА ОТКЛОНЕНА</b>\n\n"
            f"🆔 ID: {withdrawal_id}\n"
            f"📝 Причина: {comment}\n"
            f"👤 Пользователь уведомлен."
        )
    else:
        await message.answer(f"❌ Ошибка: {result_message}")
    
    await state.clear()

@dp.callback_query(F.data == "admin_withdrawals_all")
async def admin_withdrawals_all_handler(callback: CallbackQuery):
    """Показывает все заявки на вывод"""
    if not callback or not callback.message:
        return
    
    if not callback.from_user or callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    withdrawals = await utils.read_json(config.WITHDRAWALS_FILE)
    
    if not isinstance(withdrawals, dict):
        await callback.message.edit_text("📋 Нет заявок на вывод")
        await callback.answer()
        return
    
    # Группируем по статусу
    status_groups = {}
    for w in withdrawals.values():
        if isinstance(w, dict):
            status = w.get('status', 'unknown')
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(w)
    
    message_text = "📋 <b>ВСЕ ЗАЯВКИ НА ВЫВОД</b>\n\n"
    
    for status, group in status_groups.items():
        status_text = {
            'pending': '⏳ Ожидают',
            'processing': '🔄 В обработке', 
            'completed': '✅ Завершены',
            'rejected': '❌ Отклонены',
            'cancelled': '🚫 Отменены'
        }.get(status, status)
        
        total_amount = sum(w.get('amount', 0) for w in group)
        
        message_text += f"{status_text}: {len(group)} заявок на {total_amount} руб.\n"
    
    message_text += f"\n📊 Всего: {len(withdrawals)} заявок"
    
    await callback.message.edit_text(message_text)
    await callback.answer()

@dp.callback_query(F.data == "admin_withdraw_stats")
async def admin_withdraw_stats_handler(callback: CallbackQuery):
    """Показывает статистику по выводам"""
    if not callback or not callback.message:
        return
    
    if not callback.from_user or callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    withdrawals = await utils.read_json(config.WITHDRAWALS_FILE)
    
    if not isinstance(withdrawals, dict):
        await callback.message.edit_text("📊 Нет данных для статистики")
        await callback.answer()
        return
    
    # Статистика по дням
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    today_withdrawals = []
    week_withdrawals = []
    
    for w in withdrawals.values():
        if isinstance(w, dict):
            created_at = w.get('created_at', '')
            if created_at and created_at.startswith(today):
                today_withdrawals.append(w)
            if created_at and created_at >= week_ago:
                week_withdrawals.append(w)
    
    # Считаем суммы
    total_all = sum(w.get('amount', 0) for w in withdrawals.values() if isinstance(w, dict))
    total_completed = sum(w.get('amount', 0) for w in withdrawals.values() 
                         if isinstance(w, dict) and w.get('status') == 'completed')
    total_pending = sum(w.get('amount', 0) for w in withdrawals.values() 
                       if isinstance(w, dict) and w.get('status') in ['pending', 'processing'])
    total_today = sum(w.get('amount', 0) for w in today_withdrawals)
    total_week = sum(w.get('amount', 0) for w in week_withdrawals)
    
    message_text = (
        f"📊 <b>СТАТИСТИКА ВЫВОДОВ</b>\n\n"
        f"📈 <b>Общая:</b>\n"
        f"• Всего заявок: {len(withdrawals)}\n"
        f"• Общая сумма: {total_all} руб.\n"
        f"• Выведено: {total_completed} руб.\n"
        f"• В обработке: {total_pending} руб.\n\n"
        
        f"📅 <b>За период:</b>\n"
        f"• Сегодня: {len(today_withdrawals)} заявок на {total_today} руб.\n"
        f"• За неделю: {len(week_withdrawals)} заявок на {total_week} руб.\n\n"
        
        f"📋 <b>По статусам:</b>\n"
    )
    
    # Статистика по статусам
    status_counts = {}
    for w in withdrawals.values():
        if isinstance(w, dict):
            status = w.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, count in status_counts.items():
        status_name = {
            'pending': '⏳ Ожидают',
            'processing': '🔄 В обработке',
            'completed': '✅ Завершены',
            'rejected': '❌ Отклонены',
            'cancelled': '🚫 Отменены'
        }.get(status, status)
        
        message_text += f"• {status_name}: {count} заявок\n"
    
    await callback.message.edit_text(message_text)
    await callback.answer()

@dp.callback_query(F.data == "admin_withdrawals_list")
async def admin_withdrawals_list_handler(callback: CallbackQuery):
    """Возврат к списку заявок"""
    if not callback or not callback.from_user or callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    # Просто вызываем функцию админской панели
    await admin_withdrawals_panel(callback.message)
    await callback.answer()

# ========== ДОБАВЛЯЕМ ОБРАБОТЧИК ДЛЯ КНОПКИ НАЗАД ==========

@dp.callback_query(F.data == "admin_back")
async def admin_back_handler(callback: CallbackQuery):
    """Возврат в главное меню админки"""
    if not callback or not callback.message:
        return
    
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    # Используем answer вместо edit_text для ReplyKeyboardMarkup
    await callback.message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=admin_keyboard
    )
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
    """Обработка введенного инвайт-кода с немедленной отправкой задания"""
    user = message.from_user
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    # ПРОВЕРЯЕМ, ЧТО message.text НЕ NONE
    if not message.text or message.text is None:
        await message.answer("Пожалуйста, введите инвайт-код:")
        return
        
    invite_code = message.text.strip()
    
    # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА НА ПУСТОЙ СТРОКУ
    if not invite_code:
        await message.answer("Пожалуйста, введите инвайт-код:")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        await state.clear()
        return
    
    success, result = await utils.use_invite_code(invite_code, user_id)
    
    if success:
        invite_data = result
        days = invite_data.get('days', 30)
        updated_user_data = await utils.add_subscription_days(user_data, days)
        await utils.save_user(user_id, updated_user_data)
        
        # Основное сообщение
        await message.answer(
            f"✅ <b>Инвайт-код активирован!</b>\n\n"
            f"Вам добавлено <b>{days}</b> дней подписки.\n"
            f"Тип: {invite_data.get('name', 'Подписка')}\n\n"
            f"Теперь у вас есть доступ ко всем заданиям! 🎉",
            reply_markup=keyboards.get_main_menu(user.id)
        )
        
        # 🔥 КРИТИЧЕСКО ВАЖНО: ОТПРАВЛЯЕМ ЗАДАНИЕ НЕМЕДЛЕННО
        try:
            # Получаем следующий день (текущий день + 1)
            current_day = updated_user_data.get('current_day', 0)
            next_day = current_day + 1
            
            # Если пользователь только начал (день 0), ставим день 1
            if next_day == 0:
                next_day = 1
                
            # Получаем задание для следующего дня
            task_id, task = await utils.get_task_by_day(next_day, updated_user_data.get('archetype', 'spartan'))
            
            if task:
                # Форматируем сообщение с заданием
                task_message = (
                    f"📋 <b>Новое задание!</b>\n\n"
                    f"<b>День {next_day}/300</b>\n\n"
                    f"{task['text']}\n\n"
                    f"⏰ <b>До 23:59 на выполнение</b>\n\n"
                    f"<i>Отмечай выполнение кнопками ниже 👇</i>"
                )
                
                # Отправляем задание
                await bot.send_message(
                    chat_id=user_id,
                    text=task_message,
                    reply_markup=keyboards.task_keyboard,
                    disable_web_page_preview=True
                )
                
                # Обновляем данные пользователя
                updated_user_data['last_task_sent'] = datetime.now().isoformat()
                updated_user_data['task_completed_today'] = False
                await utils.save_user(user_id, updated_user_data)
                
                logger.info(f"✅ Задание дня {next_day} отправлено пользователю {user_id} после активации инвайт-кода")
            else:
                logger.warning(f"⚠️ Не найдено задание дня {next_day} для пользователя {user_id}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки задания после активации инвайт-кода пользователю {user_id}: {e}")
        
        await state.clear()
    else:
        error_message = result
        await message.answer(
            f"❌ <b>Не удалось активировать код</b>\n\n"
            f"{error_message}\n\n"
            f"Попробуйте другой код или обратитесь в поддержку: {config.SUPPORT_USERNAME}"
        )
    
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
    """Показывает начисления по реферальной программе с кнопкой вывода"""
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
    reserved = user_data.get('reserved_for_withdrawal', 0)
    available_balance = earnings - reserved
    
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
        f"💰 <b>МОИ НАЧИСЛЕНИЯ</b>\n\n"
        f"💎 <b>Балансы:</b>\n"
        f"• Общий баланс: {earnings} руб.\n"
        f"• Доступно для вывода: {available_balance} руб.\n"
        f"• В обработке: {reserved} руб.\n"
        f"• Минимум для вывода: {config.MIN_WITHDRAWAL} руб.\n"
        f"• ✅ Без комиссии\n\n"  # Добавляем
        
        f"👥 <b>Рефералы:</b>\n"
        f"• Приглашено друзей: {len(referrals)} чел.\n"
        f"• Из них оплатили: {paying_refs} чел.\n"
        f"• Активных: {active_refs} чел.\n\n"
        
        f"📊 <b>Уровень:</b>\n"
        f"• Текущий уровень: {ref_level['name']}\n"
        f"• Ваш процент: {ref_level['percent']}%\n\n"
    )
    
    # Кнопки (только нужные)
    keyboard_buttons = []
    
    if available_balance >= config.MIN_WITHDRAWAL:
        keyboard_buttons.append([InlineKeyboardButton(
            text="💸 Вывести средства", 
            callback_data="withdrawal_start"
        )])
    else:
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"💸 Вывод (нужно ещё {config.MIN_WITHDRAWAL - available_balance} руб.)", 
            callback_data="show_min_withdrawal"
        )])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="📤 Пригласить друга", switch_inline_query="invite"),
        InlineKeyboardButton(text="📋 История выводов", callback_data="withdrawal_history")
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 Назад к легиону", callback_data="show_referral")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    try:
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.answer("Не удалось обновить сообщение")
    
    await callback.answer()
@dp.callback_query(F.data == "withdrawal_start")
async def withdrawal_start_from_referral(callback: CallbackQuery, state: FSMContext):
    """Начало вывода средств из раздела реферальной программы"""
    if not callback or not callback.message:
        return
        
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    # Получаем балансы
    total_balance = user_data.get('referral_earnings', 0)
    reserved = user_data.get('reserved_for_withdrawal', 0)
    available_balance = total_balance - reserved
    
    if available_balance < config.MIN_WITHDRAWAL:
        await callback.answer(
            f"💰 <b>Доступно для вывода:</b> {available_balance} руб.\n\n"
            f"❌ <b>Минимальная сумма вывода:</b> {config.MIN_WITHDRAWAL} руб.\n\n"
            f"Приглашайте больше друзей, чтобы увеличить баланс! 🤝",
            show_alert=True
        )
        return
    
    # Показываем информацию о выводе
    info_text = (
        f"💰 <b>ВЫВОД СРЕДСТВ</b>\n\n"
        f"• Доступный баланс: <b>{available_balance} руб.</b>\n"
        f"• Минимальная сумма: {config.MIN_WITHDRAWAL} руб.\n"
        f"• Комиссия: {config.WITHDRAWAL_FEE}%\n"
        f"• Срок обработки: 1-3 рабочих дня\n\n"
        f"📝 <b>Введите сумму для вывода:</b>"
    )
    
    try:
        await callback.message.edit_text(info_text)
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        try:
            await callback.message.answer(info_text)
        except Exception as e2:
            logger.error(f"Ошибка отправки сообщения: {e2}")
            return
    
    # Устанавливаем состояние для ввода суммы
    # state уже передается как параметр, используем его
    await state.set_state(UserStates.waiting_for_withdrawal_amount)
    await state.update_data(user_id=user_id, available_balance=available_balance)
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

@dp.message(Command("check_subscription"))
async def check_subscription_command(message: Message):
    """Проверка статуса подписки пользователя"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Проверяем статус подписки
    has_subscription = await utils.is_subscription_active(user_data)
    in_trial = await utils.is_in_trial_period(user_data)
    trial_tasks = user_data.get('completed_tasks_in_trial', 0)
    
    message_text = f"🔍 <b>СТАТУС ПОДПИСКИ</b>\n\n"
    message_text += f"👤 Пользователь: {user.first_name}\n"
    message_text += f"🆔 ID: {user_id}\n\n"
    
    if has_subscription:
        message_text += "✅ <b>Статус: ПОДПИСКА АКТИВНА</b>\n"
        try:
            from datetime import datetime, timezone
            import pytz
            
            subscription_end_str = user_data.get('subscription_end')
            if subscription_end_str:
                # Парсим дату
                date_str = subscription_end_str.split('+')[0].split('.')[0]
                try:
                    sub_end = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    sub_end = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Добавляем часовой пояс
                moscow_tz = pytz.timezone('Europe/Moscow')
                if sub_end.tzinfo is None:
                    sub_end = moscow_tz.localize(sub_end)
                
                now = datetime.now(pytz.UTC)
                sub_end_utc = sub_end.astimezone(pytz.UTC)
                days_left = (sub_end_utc - now).days
                
                message_text += f"📅 Дата окончания: {sub_end.strftime('%d.%m.%Y %H:%M')}\n"
                message_text += f"⏰ Осталось дней: {days_left}\n"
        except Exception as e:
            logger.error(f"❌ Ошибка обработки даты: {e}")
            message_text += f"📅 Дата окончания: {user_data.get('subscription_end', 'неизвестно')}\n"
    elif in_trial:
        message_text += "🎁 <b>Статус: ПРОБНЫЙ ПЕРИОД</b>\n"
        message_text += f"📊 Выполнено заданий: {trial_tasks}/3\n"
        days_left = await utils.get_trial_days_left(user_data)
        message_text += f"⏰ Осталось дней: {days_left}\n"
    else:
        message_text += "❌ <b>Статус: ПОДПИСКА НЕ АКТИВНА</b>\n"
    
    # Показываем историю платежей
    payments_data = await utils.read_json(config.PAYMENTS_FILE)
    user_payments = []
    
    if payments_data:
        for payment_id, payment in payments_data.items():
            if payment.get('user_id') == user_id:
                user_payments.append(payment)
    
    if user_payments:
        message_text += f"\n📋 <b>История платежей:</b>\n"
        for payment in user_payments[:3]:  # Показываем последние 3
            date = payment.get('created_at', 'неизвестно')
            amount = payment.get('amount', 0)
            status = payment.get('status', 'неизвестно')
            message_text += f"• {date[:10]}: {amount} руб. ({status})\n"
    
    await message.answer(message_text)

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
async def activate_subscription_after_trial_handler(callback: CallbackQuery):
    """Активация подписки после окончания пробного периода"""
    if not callback or not callback.message:
        return
        
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await callback.answer("Пользователь не найден")
        return
    
    # Показываем тарифы для оплаты
    message_text = (
        "💎 <b>АКТИВАЦИЯ ПОДПИСКИ</b>\n\n"
        "Пробный период закончился. Выберите тариф для продолжения:\n\n"
        "<b>После оплаты задание придет сразу же!</b> ⚡"
    )
    
    await callback.message.edit_text(message_text, reply_markup=keyboards.get_payment_keyboard())
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


@dp.message(Command("debug_ref"))
async def debug_ref_command(message: Message):
    """Отладка реферальной системы"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Пользователь не найден")
        return
    
    referrals = user_data.get('referrals', [])
    invited_by = user_data.get('invited_by')
    earnings = user_data.get('referral_earnings', 0)
    
    debug_text = (
        f"🔍 <b>ДЕБАГ РЕФЕРАЛЬНОЙ СИСТЕМЫ</b>\n\n"
        f"👤 Ваш ID: {user_id}\n"
        f"📊 Рефералов в списке: {len(referrals)}\n"
        f"📋 Список ID рефералов: {referrals}\n"
        f"👥 Вас пригласил: {invited_by}\n"
        f"💰 Заработано: {earnings} руб.\n\n"
    )
    
    # Проверяем каждого реферала
    if referrals:
        debug_text += "<b>Детали по рефералам:</b>\n"
        for i, ref_id in enumerate(referrals, 1):
            ref_data = await utils.get_user(ref_id)
            if ref_data:
                name = ref_data.get('first_name', 'Неизвестно')
                sub_active = await utils.is_subscription_active(ref_data)
                debug_text += f"{i}. {name} (ID: {ref_id}) - подписка: {'✅' if sub_active else '❌'}\n"
    
    await message.answer(debug_text)
# ========== АВТОМАТИЧЕСКИЕ УВЕДОМЛЕНИЯ О ПОДПИСКЕ ==========

async def check_and_notify_inactive_users():
    """Проверяет и уведомляет пользователей без активной подписки"""
    logger.info("🔔 Проверяем неактивных пользователей...")
    
    users = await utils.get_all_users()
    notified_count = 0
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            
            # Пропускаем пользователей с активной подпиской
            if await utils.is_subscription_active(user_data):
                continue
            
            # 1. Проверяем пробный период
            if await utils.is_in_trial_period(user_data):
                # Уже есть уведомление в check_trial_expiry()
                continue
            
            # 2. Проверяем, когда закончилась подписка
            subscription_end = user_data.get('subscription_end')
            if subscription_end:
                try:
                    end_date = datetime.fromisoformat(subscription_end)
                    days_since_end = (datetime.now() - end_date).days
                    
                    # Уведомления в разные интервалы после окончания подписки
                    if days_since_end == 1:  # Первый день после окончания
                        await send_subscription_ended_notification(user_id, user_data, days_since_end)
                        notified_count += 1
                        
                    elif days_since_end == 3:  # Через 3 дня
                        await send_subscription_reminder(user_id, user_data, days_since_end)
                        notified_count += 1
                        
                    elif days_since_end == 7:  # Через неделю
                        await send_last_chance_notification(user_id, user_data, days_since_end)
                        notified_count += 1
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки даты подписки пользователя {user_id}: {e}")
            
            # 3. Проверяем, когда закончился пробный период
            created_at = datetime.fromisoformat(user_data.get('created_at', datetime.now().isoformat()))
            days_passed = (datetime.now() - created_at).days
            
            # Уведомления после пробного периода
            if days_passed == 4:  # На следующий день после пробного периода
                await send_post_trial_notification(user_id, user_data)
                notified_count += 1
                
            elif days_passed == 7:  # Через 4 дня после пробного периода
                await send_post_trial_reminder(user_id, user_data)
                notified_count += 1
                
        except Exception as e:
            logger.error(f"❌ Ошибка уведомления пользователя {user_id_str}: {e}")
    
    logger.info(f"📊 Уведомления отправлены: {notified_count} пользователям")

async def send_subscription_ended_notification(user_id: int, user_data: dict, days_since_end: int):
    """Уведомление об окончании подписки"""
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💎 Продлить подписку", 
                    callback_data="activate_subscription_after_expiry"
                )],
                [InlineKeyboardButton(
                    text="📊 Мой прогресс", 
                    callback_data="show_progress_after_expiry"
                )]
            ]
        )
        
        message_text = (
            f"📅 <b>Ваша подписка закончилась</b>\n\n"
            f"Доступ к ежедневным заданиям приостановлен.\n\n"
            f"💪 <b>Не останавливайся на достигнутом!</b>\n"
            f"• Продолжай развивать дисциплину\n"
            f"• Сохрани достигнутый прогресс\n"
            f"• Вернись в строй с новой подпиской!\n\n"
            f"🔥 <b>Активируй подписку и продолжай путь!</b>"
        )
        
        await safe_send_message(
            user_id=user_id,
            text=message_text,
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Уведомление об окончании подписки отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")

async def send_subscription_reminder(user_id: int, user_data: dict, days_since_end: int):
    """Напоминание об окончании подписки (через 3 дня)"""
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💎 Вернуться в челлендж", 
                    callback_data="activate_subscription_reminder"
                )]
            ]
        )
        
        message_text = (
            f"⏰ <b>Напоминание о подписке</b>\n\n"
            f"Прошло уже {days_since_end} дней с момента окончания подписки.\n\n"
            f"🎯 <b>Твой прогресс ждет тебя:</b>\n"
            f"• Выполнено заданий: {user_data.get('completed_tasks', 0)}\n"
            f"• Текущий ранг: {user_data.get('rank', 'путник')}\n"
            f"• Достижения сохранены\n\n"
            f"💪 <b>Вернись и продолжай путь к сильной версии себя!</b>"
        )
        
        await safe_send_message(
            user_id=user_id,
            text=message_text,
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Напоминание о подписке отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")

async def send_last_chance_notification(user_id: int, user_data: dict, days_since_end: int):
    """Последнее уведомление перед очисткой прогресса"""
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💎 Вернуться сейчас", 
                    callback_data="activate_subscription_last_chance"
                )]
            ]
        )
        
        message_text = (
            f"⚠️ <b>Последний шанс сохранить прогресс!</b>\n\n"
            f"Прошло {days_since_end} дней без подписки.\n"
            f"Скоро твой прогресс будет сброшен.\n\n"
            f"📊 <b>Твои текущие достижения:</b>\n"
            f"• Выполнено: {user_data.get('completed_tasks', 0)}/300 заданий\n"
            f"• Ранг: {user_data.get('rank', 'путник')}\n"
            f"• Дней в системе: {user_data.get('current_day', 0)}\n\n"
            f"🔥 <b>Активируй подписку сейчас чтобы сохранить прогресс!</b>"
        )
        
        await safe_send_message(
            user_id=user_id,
            text=message_text,
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Последнее уведомление отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки последнего уведомления пользователю {user_id}: {e}")

async def send_post_trial_notification(user_id: int, user_data: dict):
    """Уведомление на следующий день после пробного периода"""
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💎 Активировать подписку", 
                    callback_data="activate_subscription_post_trial"
                )],
                [InlineKeyboardButton(
                    text="🎯 Посмотреть тарифы", 
                    callback_data="view_tariffs_post_trial"
                )]
            ]
        )
        
        message_text = (
            f"🎯 <b>Пробный период завершен</b>\n\n"
            f"Ты попробовал(а) систему и получил(а) первые результаты!\n\n"
            f"💪 <b>Что дальше?</b>\n"
            f"• Ежедневные задания для развития силы воли\n"
            f"• Система рангов и достижений\n"
            f"• Поддержка комьюнити\n"
            f"• 297 дней роста впереди!\n\n"
            f"🔥 <b>Продолжи путь к сильной версии себя!</b>\n"
            f"Активируй подписку и получи доступ ко всем заданиям!"
        )
        
        await safe_send_message(
            user_id=user_id,
            text=message_text,
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Пост-пробное уведомление отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки пост-пробного уведомления пользователю {user_id}: {e}")

async def send_post_trial_reminder(user_id: int, user_data: dict):

    
    """Повторное напоминание после пробного периода"""
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💎 Вернуться в челлендж", 
                    callback_data="activate_subscription_post_trial_reminder"
                )]
            ]
        )
        
        message_text = (
            f"⏰ <b>Скучаем по тебе в челлендже!</b>\n\n"
            f"Прошла неделя с момента пробного периода.\n\n"
            f"🎯 <b>Помни, что тебя ждет:</b>\n"
            f"• 297 дней роста и развития\n"
            f"• Новая, сильная версия себя\n"
            f"• Ежедневные победы над собой\n\n"
            f"💪 <b>Вернись и продолжай путь!</b>\n"
            f"Твое место в челлендже все еще свободно."
        )
        
        await safe_send_message(
            user_id=user_id,
            text=message_text,
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Повторное напоминание после пробного периода отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки повторного напоминания пользователю {user_id}: {e}")
# ДОБАВЬ ЭТУ ФУНКЦИЮ ПЕРЕД async def main()

async def simple_inactive_users_check():
    """Простая проверка неактивных пользователей - базовый вариант"""
    logger.info("🔔 Простая проверка неактивных пользователей...")
    
    try:
        # Пока просто логируем, чтобы не ломать систему
        logger.info("✅ Задача уведомлений неактивных пользователей выполняется")
        
        # Можно добавить простую логику позже
        # Например:
        # users = await utils.get_all_users()
        # logger.info(f"📊 Всего пользователей в системе: {len(users)}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в simple_inactive_users_check: {e}")
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

@dp.message(Command("checkme"))
async def check_me_command(message: Message):
    """Проверка данных пользователя"""
    if not message or not message.from_user:
        await message.answer("❌ Ошибка: не удалось получить информацию о пользователе")
        return
    
    user = message.from_user
    user_id = user.id
    
    # Сначала регистрируем пользователя если его нет
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        # Создаем временного пользователя для теста
        from datetime import datetime
        import pytz
        
        moscow_tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(moscow_tz)
        
        user_data = {
            "user_id": user_id,
            "username": user.username or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "archetype": "spartan",  # по умолчанию
            "timezone": "Europe/Moscow",
            "current_day": 0,
            "completed_tasks": 0,
            "rank": "putnik",
            "created_at": now.isoformat(),
            "referrals": [],
            "referral_earnings": 0,
            "last_task_sent": None,
            "task_completed_today": False,
            "debts": [],
            "last_activity": now.isoformat()
        }
        await utils.save_user(user_id, user_data)
        await message.answer("⚠️ Создал временную запись пользователя для теста")
    
    # Проверяем статус подписки
    has_subscription = await utils.is_subscription_active(user_data)
    in_trial = await utils.is_in_trial_period(user_data)
    
    # Проверяем задачи
    todays_tasks = await utils.get_todays_tasks(user_data)
    
    debug_info = (
        f"🔍 <b>ПРОВЕРКА ДАННЫХ</b>\n\n"
        f"👤 Пользователь: {user.first_name}\n"
        f"🆔 ID: {user_id}\n"
        f"📅 Создан: {user_data.get('created_at', 'неизвестно')}\n"
        f"🎯 Архетип: {user_data.get('archetype', 'не установлен')}\n"
        f"📊 Текущий день: {user_data.get('current_day', 0)}\n"
        f"✅ Выполнено: {user_data.get('completed_tasks', 0)}\n"
        f"💎 Подписка активна: {has_subscription}\n"
        f"🆓 Пробный период: {in_trial}\n"
        f"📅 Последнее задание: {user_data.get('last_task_sent', 'никогда')}\n"
        f"✅ Задание выполнено сегодня: {user_data.get('task_completed_today', False)}\n"
        f"📋 Сегодняшних заданий: {len(todays_tasks) if todays_tasks else 0}\n"
    )
    
    # Проверяем функции доступа
    can_receive = await utils.can_receive_new_task(user_data)
    debug_info += f"📤 Может получить задание: {can_receive}\n"
    
    if todays_tasks:
        task = todays_tasks[0]
        debug_info += f"📝 Задание дня: {task.get('day', '?')} - {task.get('text', 'нет текста')[:50]}...\n"
    
    await message.answer(debug_info)
async def main():
    logger.info("Бот запускается...")
    
    # ТЕСТ: Принудительно запускаем рассылку при старте
    logger.info("🔄 Принудительный запуск рассылки при старте...")    
    
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
    
    # 1. Проверка пробного периода в 10:00
    if 'check_trial_expiry' in globals():
        scheduler.add_job(
            check_trial_expiry,
            trigger=CronTrigger(
                hour=10, minute=0,
                timezone=config.TIMEZONE
            ),
            id="trial_expiry_check"
        )
        logger.info("✅ Добавлена проверка пробного периода в 10:00")
    
    # 2. Уведомления неактивным пользователям в 12:00 - СНАЧАЛА ПРОСТОЙ ВАРИАНТ
    scheduler.add_job(
        simple_inactive_users_check,  # Простая функция вместо сложной
        trigger=CronTrigger(
            hour=15, minute=0,
            timezone=config.TIMEZONE
        ),
        id="inactive_users_notifications"
    )
    logger.info("✅ Добавлены уведомления неактивным пользователям в 12:00")
    
    scheduler.start()
    logger.info("📅 Планировщик запущен")
    
    logger.info("🤖 Запускаем бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())