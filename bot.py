import asyncio
import logging
import payments
from datetime import datetime
import random
import math 
import os
import shutil
from aiogram import F
from aiogram.filters import StateFilter
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
    # Новые состояния для создания сертификатов
    admin_waiting_certificate_type = State()
    admin_waiting_certificate_days = State()
    admin_waiting_certificate_recipient = State()  # для кого сертификат
    admin_waiting_certificate_message = State()  # персональное сообщение
    # Новые состояния для массовой рассылки
    admin_waiting_mass_text = State()
    admin_waiting_mass_confirm = State()
    admin_waiting_mass_photo = State()
    admin_viewing_mass_history = State()


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
class RankNotifications:
    """Класс для красивых уведомлений о системе рангов"""
    
    @staticmethod
    async def send_rank_up_notification(bot, user_id: int, old_rank: str, new_rank: str, user_data: dict):
        """Отправляет красивое уведомление о повышении ранга"""
        try:
            # Получаем информацию о рангах
            old_rank_info = await utils.get_rank_info(old_rank)
            new_rank_info = await utils.get_rank_info(new_rank)
            
            if not old_rank_info or not new_rank_info:
                return
            
            completed_tasks = user_data.get('completed_tasks', 0)
            
            # Красивое сообщение с эмодзи
            message_text = (
                f"🎉 <b>ПОЗДРАВЛЯЕМ С ПОВЫШЕНИЕМ РАНГА!</b>\n\n"
                
                f"🏆 <b>{old_rank_info.get('name', 'Старый ранг')} → {new_rank_info.get('name', 'Новый ранг')}</b>\n\n"
                
                f"📊 <b>Твой прогресс:</b>\n"
                f"• Выполнено заданий: {completed_tasks}/300\n"
                f"• Новый вызов: {new_rank_info.get('description', '')}\n\n"
            )
            
            # Добавляем привилегии нового ранга
            privileges = new_rank_info.get('privileges', [])
            if privileges:
                message_text += "🎁 <b>Новые привилегии:</b>\n"
                for i, privilege in enumerate(privileges, 1):
                    message_text += f"{i}. {privilege}\n"
                message_text += "\n"
            
            # Добавляем мотивацию для следующего ранга
            next_rank = await utils.get_next_rank_info(new_rank)
            if next_rank:
                tasks_needed = next_rank.get('completed_tasks', 0) - completed_tasks
                message_text += (
                    f"🎯 <b>До {next_rank.get('name', 'следующего ранга')}:</b> {tasks_needed} заданий\n\n"
                )
            
            # Итоговое поздравление
            message_text += (
                f"💪 <b>Так держать! Ты становишься сильнее с каждым днем!</b>\n"
                f"Продолжай выполнять задания и открывай новые возможности!"
            )
            
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode='HTML'
            )
            
            logger.info(f"✅ Красивое уведомление о ранге отправлено пользователю {user_id}: {old_rank} → {new_rank}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о ранге: {e}")
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
# В функции send_daily_tasks обновим логику отправки обычных заданий:
async def check_and_auto_skip_expired_blocks():
    """Проверяет и автоматически пропускает задания, по которым не ответили более 24 часов""" 
    logger.info("⏰ Проверяем просроченные блокировки...")
    
    users = await utils.get_all_users()
    auto_skipped_count = 0
    
    default_timezone = pytz.timezone(config.TIMEZONE)
    now = datetime.now(default_timezone)
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            
            # Пропускаем неактивных
            has_subscription = await utils.is_subscription_active(user_data)
            in_trial = await utils.is_in_trial_period(user_data)
            
            if not has_subscription and not in_trial:
                continue
            
            needs_to_complete_yesterday = user_data.get('needs_to_complete_yesterday', False)
            blocked_since_str = user_data.get('blocked_since')
            
            if needs_to_complete_yesterday and blocked_since_str:
                try:
                    # Получаем часовой пояс пользователя
                    user_timezone_str = user_data.get('timezone', config.TIMEZONE)
                    try:
                        user_timezone = pytz.timezone(user_timezone_str)
                    except:
                        user_timezone = default_timezone
                    
                    blocked_since_utc = datetime.fromisoformat(blocked_since_str)
                    if blocked_since_utc.tzinfo is None:
                        blocked_since_utc = pytz.UTC.localize(blocked_since_utc)
                    
                    blocked_since_user = blocked_since_utc.astimezone(user_timezone)
                    user_now = now.astimezone(user_timezone)
                    
                    hours_passed = (user_now - blocked_since_user).total_seconds() / 3600
                    
                    # Если прошло от 24 до 48 часов - авто-пропуск
                    if 24 <= hours_passed < 48:
                        # Автоматически пропускаем задание
                        user_data['needs_to_complete_yesterday'] = False
                        user_data['current_day'] = user_data.get('current_day', 0) + 1
                        
                        # Увеличиваем счетчик пробных заданий
                        if in_trial:
                            trial_tasks = user_data.get('completed_tasks_in_trial', 0)
                            user_data['completed_tasks_in_trial'] = trial_tasks + 1
                            
                            if trial_tasks + 1 >= 3:
                                user_data['trial_finished'] = True
                        
                        await utils.save_user(user_id, user_data)
                        auto_skipped_count += 1
                        
                        logger.info(f"🔄 Авто-пропуск задания для {user_id} ({hours_passed:.1f} часов)")
                        
                        # Отправляем уведомление
                        try:
                            message = (
                                "⏰ <b>Задание автоматически пропущено</b>\n\n"
                                f"Ты не ответил на предыдущее задание в течение {hours_passed:.0f} часов.\n"
                                "Мы автоматически отметили его как пропущенное.\n\n"
                                "📅 <b>Твой прогресс сохранен!</b>\n\n"
                                "💡 <b>Совет:</b> Отвечай на задания вовремя, чтобы не терять мотивацию!"
                            )
                            
                            await safe_send_message(user_id, message)
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки уведомления авто-пропуска {user_id}: {e}")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки авто-пропуска для {user_id}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обработки пользователя {user_id_str}: {e}")
    
    if auto_skipped_count > 0:
        logger.info(f"✅ Авто-пропущено заданий: {auto_skipped_count}")

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
            f"⏰ <b>Выполни задание до 23:59</b>\n\n"
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
                    f"<i>Выполни задание до 23:59</i>"
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

async def backup_users_data():
    """Создаёт операционный бэкап с меткой времени"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "/home/botuser/backups_operational"
    os.makedirs(backup_dir, exist_ok=True)

    # Копируем файлы
    for filename in ["users_data.json", "stages.json", "payments_data.json", "invite_codes.json"]:
        src = f"/home/botuser/telegram-bot/{filename}"
        dst = f"{backup_dir}/{filename}_{timestamp}.json"
        if os.path.exists(src):
            shutil.copy2(src, dst)

    # Удаляем бэкапы старше 24 часов
    cleanup_old_backups(backup_dir, hours=24)

def cleanup_old_backups(backup_dir, hours=24):
    """Удаляет бэкапы старше N часов"""
    now = datetime.now()
    for filename in os.listdir(backup_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(backup_dir, filename)
            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if (now - file_time).total_seconds() > hours * 3600:
                os.remove(file_path)

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start с реферальной системой - ПЕРЕПИСАННАЯ"""
    try:
        # Проверяем наличие пользователя
        user = message.from_user
        if not user:
            logger.error("❌ cmd_start: Не удалось получить информацию о пользователе")
            await message.answer("Ошибка: не удалось получить информацию о пользователе")
            return
        
        # Логируем начало регистрации
        logger.info(f"🚀 Начало регистрации: {user.id} (@{user.username or 'нет'}) - {user.first_name}")
        
        # Получаем аргументы команды /start
        args = message.text.split() if message.text else []
        referrer_id = None
        
        # Проверяем реферальный ID (если есть в аргументах)
        if len(args) > 1:
            try:
                referrer_id = int(args[1])
                logger.info(f"📝 Реферальный переход: {user.id} -> от {referrer_id}")
                
                # Проверяем, что реферер существует и не является самим пользователем
                if referrer_id == user.id:
                    logger.warning(f"⚠️ Пользователь {user.id} пытается пригласить себя")
                    referrer_id = None
                else:
                    # Проверяем существование реферера
                    referrer_data = await utils.get_user(referrer_id)
                    if not referrer_data:
                        logger.warning(f"⚠️ Реферер {referrer_id} не найден в базе")
                        referrer_id = None
                        
            except ValueError as e:
                logger.warning(f"⚠️ Неверный реферальный ID '{args[1]}': {e}")
                referrer_id = None
        
        # Очищаем состояние FSM
        try:
            await state.clear()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка очистки состояния: {e}")
        
        # Проверяем, есть ли уже пользователь в базе
        user_data = await utils.get_user(user.id)
        
        if user_data:
            # ✅ ПОЛЬЗОВАТЕЛЬ УЖЕ ЗАРЕГИСТРИРОВАН
            
            # Получаем гендерные окончания
            gender = await utils.get_gender_ending(user_data)
            welcome_name = user.first_name or "Путник"
            
            # Получаем случайную реплику приветствия
            greeting = await BotReplies.get_welcome_back_reply(gender, welcome_name)
            
            # Проверяем и восстанавливаем реферальную связь если нужно
            if referrer_id and not user_data.get('invited_by'):
                success = await utils.save_referral_relationship(user.id, referrer_id)
                if success:
                    logger.info(f"✅ Восстановлена реферальная связь: {user.id} -> {referrer_id}")
            
            # Обновляем активность
            await utils.update_user_activity(user.id)
            
            # Отправляем приветствие
            await message.answer(
                greeting,
                reply_markup=keyboards.get_main_menu(user.id),
                disable_web_page_preview=True
            )
            
            logger.info(f"✅ Возврат пользователя {user.id} в систему")
            
        else:
            # ❌ НОВЫЙ ПОЛЬЗОВАТЕЛЬ - начинаем регистрацию
            
            logger.info(f"👤 Новый пользователь: {user.id} (@{user.username or 'нет'})")
            
            # Приветственное сообщение
            await message.answer(
                "👋 <b>Приветствую, путник!</b>\n\n"
                "• 300 ПИНКОВ — это система, которая заставляет мозг и тело работать по-новому.\n\n"
                
                "🎯 <b>Что тебя ждет:</b>\n"
                "• Ежедневные задания\n"
                "• 300 дней непрерывного роста\n"
                "• Система рангов и привилегий\n\n"
                
                "💪 <b>Как это работает:</b>\n"
                "• В 9:00 — получаешь ПИНОК\n"
                "• До 23:59 — выполняешь\n"
                "• Честность = прогресс\n\n"
                
                "⬇️ <b>Давай настроим твой челлендж!</b>",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="➡️ Продолжить настройку")]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                ),
                disable_web_page_preview=True
            )
            
            # Сохраняем реферальный ID в состоянии
            if referrer_id:
                await state.update_data(referrer_id=referrer_id)
                logger.info(f"📝 Сохранен реферальный ID {referrer_id} для пользователя {user.id}")
            
            # Переходим к выбору часового пояса
            await state.set_state(UserStates.waiting_for_timezone)
            logger.info(f"📋 Пользователь {user.id} перешел к выбору часового пояса")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в cmd_start: {e}", exc_info=True)
        
        # Отправляем сообщение об ошибке
        try:
            await message.answer(
                "❌ <b>Произошла ошибка при запуске</b>\n\n"
                "Попробуйте снова через несколько минут.\n"
                "Если проблема повторяется, обратитесь в поддержку.",
                reply_markup=ReplyKeyboardRemove()
            )
        except:
            pass
        
        # Очищаем состояние
        try:
            await state.clear()
        except:
            pass
      

@dp.message(UserStates.waiting_for_timezone, F.text == "➡️ Продолжить настройку")
async def process_timezone_step(message: Message, state: FSMContext):
    """ШАГ 2: Выбор часового пояса"""
    from keyboards import get_timezone_keyboard
    
    await message.answer(
        "🕐 <b>Выбери свой часовой пояс:</b>\n\n"
        "ПИНОК придёт ровно в 9:00 по твоему местному времени.",
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
    
    "⚔️ <b>Спартанец (мужской путь)</b>\n" 
    "• Лидерство и ответственность\n"
    "• Мужские вызовы и дисциплина\n\n"

    "🛡️ <b>Амазонка (женский путь)</b>\n"
    "• Осознанность и женская энергия\n"
    "• Женские практики и самопознание\n\n"
    
    "🎯 <b>Важно:</b>\n"
    "• Задания адаптированы под гендерные особенности\n"
    "• Учтены психологические различия\n\n"
    
    "⬇️ <b>Какой путь твой?</b>",
    reply_markup=archetype_keyboard
)
    await state.set_state(UserStates.waiting_for_archetype)

@dp.message(UserStates.waiting_for_ready)
async def process_ready_confirmation(message: Message, state: FSMContext):
    """ШАГ 6: Обработка подтверждения готовности - ПЕРЕПИСАННАЯ"""
    try:
        # Проверяем пользователя
        user = message.from_user
        if not user:
            await message.answer("❌ Ошибка: не удалось получить информацию о пользователе")
            await state.clear()
            return
        
        user_id = user.id
        logger.info(f"📝 Подтверждение готовности от пользователя {user_id}")
        
        # Получаем данные из состояния
        user_data = await state.get_data()
        archetype = user_data.get('archetype', 'spartan')
        
        # Определяем текст кнопок в зависимости от архетипа
        if archetype == "spartan":
            yes_button_text = "✅ Да, я готов начать!"
            no_button_text = "❌ Нет, я передумал"
            gender_text = "воин"
        else:
            yes_button_text = "✅ Да, я готова начать!"
            no_button_text = "❌ Нет, я передумала"
            gender_text = "воительница"
        
        # Проверяем ответ пользователя
        if not message.text:
            await message.answer(f"Пожалуйста, выбери вариант кнопкой ниже:")
            return
        
        # Обработка отказа
        if message.text == no_button_text:
            await message.answer(
                f"Хорошо, {gender_text}. Если захочешь измениться - всегда ждем тебя! 👋\n"
                f"Просто снова нажми /start когда будешь готов{'' if archetype == 'spartan' else 'а'}.",
                reply_markup=ReplyKeyboardRemove()
            )
            
            logger.info(f"❌ Пользователь {user_id} отказался от регистрации")
            await state.clear()
            return
        
        # Проверяем подтверждение готовности
        if message.text != yes_button_text:
            await message.answer(f"Пожалуйста, подтверди готовность кнопкой ниже:")
            return
        
        # ✅ ПОЛЬЗОВАТЕЛЬ ПОДТВЕРДИЛ ГОТОВНОСТЬ
        
        logger.info(f"✅ Пользователь {user_id} подтвердил готовность. Начинаем регистрацию...")
        
        # Получаем все сохраненные данные
        timezone = user_data.get('timezone', 'Europe/Moscow')
        referrer_id = user_data.get('referrer_id')
        
        # Создаем запись пользователя
        new_user_data = {
            "user_id": user_id,
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
            },
            "completed_tasks_in_trial": 0,
            "trial_finished": False
        }
        
        # 🔐 АТОМАРНОЕ СОХРАНЕНИЕ ПОЛЬЗОВАТЕЛЯ
        try:
            # Читаем текущих пользователей
            users = await utils.atomic_read_json(config.USERS_FILE)
            if not isinstance(users, dict):
                users = {}
            
            # Добавляем нового пользователя
            users[str(user_id)] = new_user_data
            
            # Сохраняем атомарно
            await utils.atomic_write_json(config.USERS_FILE, users)
            
            logger.info(f"💾 Пользователь {user_id} сохранен в базу. Всего пользователей: {len(users)}")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка сохранения пользователя {user_id}: {e}")
            
            # Пробуем сохранить через emergency функцию
            try:
                await utils.emergency_save_user(user_id, new_user_data)
                logger.info(f"🚨 Пользователь {user_id} сохранен через emergency функцию")
            except Exception as emergency_error:
                logger.error(f"❌ Не удалось сохранить даже через emergency: {emergency_error}")
                raise Exception(f"Не удалось сохранить пользователя: {e}")
        
        # 💾 СОЗДАЕМ BACKUP ПОСЛЕ УСПЕШНОГО СОХРАНЕНИЯ
        try:
            logger.info(f"💾 Создаю backup после регистрации пользователя {user_id}")
            await backup_users_data()
            logger.info(f"✅ Backup создан успешно")
        except Exception as backup_error:
            logger.error(f"⚠️ Ошибка создания backup: {backup_error}")
            # Не прерываем процесс, только логируем
        
        # 🤝 СОХРАНЯЕМ РЕФЕРАЛЬНУЮ СВЯЗЬ
        if referrer_id:
            success = await utils.save_referral_relationship(user_id, referrer_id)
            if success:
                logger.info(f"✅ Реферальная связь сохранена: {user_id} -> {referrer_id}")
                
                # Уведомляем реферера
                try:
                    referrer_name = new_user_data.get('first_name', 'Новый пользователь')
                    welcome_msg = (
                        f"🎉 <b>Новый реферал!</b>\n\n"
                        f"По твоей ссылке присоединился {referrer_name}!\n"
                        f"Когда он оплатит подписку - ты получишь бонус!"
                    )
                    
                    await bot.send_message(referrer_id, welcome_msg)
                except Exception as notify_error:
                    logger.error(f"⚠️ Не удалось уведомить реферера {referrer_id}: {notify_error}")
            else:
                logger.error(f"❌ Не удалось сохранить реферальную связь")
        
        # 📝 ЛОГИРУЕМ УСПЕШНУЮ РЕГИСТРАЦИЮ
        logger.info(f"🎉 УСПЕШНАЯ РЕГИСТРАЦИЯ: {user_id}, архетип: {archetype}")
        logger.info(f"   📅 Создан: {new_user_data['created_at']}")
        logger.info(f"   🕐 Часовой пояс: {timezone}")
        logger.info(f"   🤝 Реферер: {referrer_id if referrer_id else 'нет'}")
        
        # 🎯 ОТПРАВЛЯЕМ ПРИВЕТСТВЕННОЕ СООБЩЕНИЕ
        if archetype == "spartan":
            welcome_message = (
                "🎯 <b>ДОБРО ПОЖАЛОВАТЬ, ПУТНИК!</b>\n\n"
                "Ты выбрал путь силы и дисциплины.\n\n"
                "Теперь ты часть древней Спарты - людей, которые "
                "своей волей и упорством создавали легенды.\n\n"
                "💪 <b>Твои принципы:</b>\n"
                "• Ответственность за себя\n"
                "• Ежедневное преодоление\n"
                "• Честь и достоинство\n\n"
            )
        else:
            welcome_message = (
                "🎯 <b>ДОБРО ПОЖАЛОВАТЬ, ВОИТЕЛЬНИЦА!</b>\n\n"
                "Ты выбрала путь гармонии и внутренней силы.\n\n"
                "Теперь ты часть общества Амазонок - женщин, которые "
                "сочетают в себе грацию, мудрость и непоколебимую силу.\n\n"
                "🌸 <b>Твои принципы:</b>\n"
                "• Осознанность и интуиция\n"
                "• Баланс мягкости и стойкости\n"
                "• Самоуважение и мудрость\n\n"
            )
        
        # 📋 ОТПРАВЛЯЕМ ПЕРВОЕ ЗАДАНИЕ
        try:
            task_id, task = await utils.get_task_by_day(1, archetype)
            
            if task:
                gender_ending = "ТВОЕ" if archetype == "spartan" else "ТВОЁ"
                time_text = "у тебя" if archetype == "spartan" else "у тебя"
                
                task_message = (
                    f"{welcome_message}"
                    f"<b>{gender_ending} ПЕРВОЕ ЗАДАНИЕ!</b>\n\n"
                    f"<b>День 1/300</b>\n\n"
                    f"{task['text']}\n\n"
                    f"💪 Начало твоего пути к сильной версии себя!\n"
                    f"⏰ У тебя есть время до 23:59 на выполнение\n\n"
                    f"<i>Отмечай выполнение кнопками ниже 👇</i>"
                )
                
                await message.answer(
                    task_message,
                    reply_markup=keyboards.task_keyboard,
                    disable_web_page_preview=True
                )
                
                # Обновляем данные пользователя
                new_user_data['last_task_sent'] = datetime.now().isoformat()
                new_user_data['task_completed_today'] = False
                
                # Сохраняем обновленные данные
                await utils.save_user(user_id, new_user_data)
                
                logger.info(f"✅ Первое задание отправлено пользователю {user_id}")
                
            else:
                # Если задание не найдено
                await message.answer(
                    f"{welcome_message}"
                    "К сожалению, первое задание временно недоступно.\n"
                    "Мы уже работаем над решением проблемы.\n\n"
                    "А пока можешь ознакомиться с функциями бота:",
                    reply_markup=keyboards.get_main_menu(user_id)
                )
                logger.warning(f"⚠️ Не найдено задание дня 1 для пользователя {user_id}")
                
        except Exception as task_error:
            logger.error(f"❌ Ошибка отправки задания: {task_error}")
            
            await message.answer(
                f"{welcome_message}"
                "Произошла ошибка при загрузке задания.\n"
                "Попробуй обновить меню через кнопку 'Задание на сегодня'.",
                reply_markup=keyboards.get_main_menu(user_id)
            )
        
        # 📱 ПОКАЗЫВАЕМ ГЛАВНОЕ МЕНЮ
        gender_ending_menu = "Тебе" if archetype == "spartan" else "Тебе"
        await message.answer(
            f"📋 <b>Теперь {gender_ending_menu.lower()} доступны все функции бота!</b>\n\n"
            "Используй меню ниже для навигации:",
            reply_markup=keyboards.get_main_menu(user_id)
        )
        
        # 🔄 ОБНОВЛЯЕМ АКТИВНОСТЬ
        await utils.update_user_activity(user_id)
        
        # 🧹 ОЧИЩАЕМ СОСТОЯНИЕ
        await state.clear()
        
        logger.info(f"✅ Регистрация пользователя {user_id} завершена успешно")
        
        # 📊 УВЕДОМЛЯЕМ АДМИНА О НОВОМ ПОЛЬЗОВАТЕЛЕ
        try:
            admin_message = (
                f"👤 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ</b>\n\n"
                f"📛 {user.first_name} (@{user.username or 'нет'})\n"
                f"🆔 {user_id}\n"
                f"🎯 Архетип: {'🛡️ Спартанец' if archetype == 'spartan' else '⚔️ Амазонка'}\n"
                f"🕐 Часовой пояс: {timezone}\n"
                f"🤝 Реферер: {referrer_id if referrer_id else 'нет'}\n"
                f"📅 Время: {datetime.now().strftime('%H:%M:%S')}"
            )
            await bot.send_message(config.ADMIN_ID, admin_message)
        except Exception as admin_error:
            logger.error(f"⚠️ Не удалось уведомить админа: {admin_error}")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в process_ready_confirmation: {e}", exc_info=True)
        
        # Отправляем сообщение об ошибке
        try:
            await message.answer(
                "❌ <b>Произошла ошибка при регистрации</b>\n\n"
                "Пожалуйста, попробуй снова через несколько минут.\n"
                "Если проблема повторяется, обратись в поддержку.",
                reply_markup=ReplyKeyboardRemove()
            )
        except:
            pass
        
        # Очищаем состояние
        try:
            await state.clear()
        except:
            pass
@dp.message(UserStates.waiting_for_archetype)
async def process_archetype(message: Message, state: FSMContext):
    """Обработка выбора архетипа - ЗАДАНИЕ СРАЗУ ПОСЛЕ ВЫБОРА"""
    try:
        if not message or not message.from_user:
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
        
        user = message.from_user
        user_id = user.id
        
        logger.info(f"✅ Пользователь {user_id} выбрал архетип: {archetype}")
        
        # Получаем все сохраненные данные из состояния
        user_data = await state.get_data()
        timezone = user_data.get('timezone', 'Europe/Moscow')
        referrer_id = user_data.get('referrer_id')
        
        # ========== СОЗДАЕМ ПОЛЬЗОВАТЕЛЯ ==========
        new_user_data = {
            "user_id": user_id,
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
            },
            "completed_tasks_in_trial": 0,
            "trial_finished": False
        }
        
        # Сохраняем пользователя
        try:
            users = await utils.atomic_read_json(config.USERS_FILE)
            if not isinstance(users, dict):
                users = {}
            users[str(user_id)] = new_user_data
            await utils.atomic_write_json(config.USERS_FILE, users)
            logger.info(f"💾 Пользователь {user_id} сохранен в базу")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя {user_id}: {e}")
            await message.answer("❌ Ошибка регистрации. Попробуйте позже.")
            await state.clear()
            return
        
        # Сохраняем реферальную связь
        if referrer_id:
            success = await utils.save_referral_relationship(user_id, referrer_id)
            if success:
                logger.info(f"✅ Реферальная связь сохранена: {user_id} -> {referrer_id}")
                try:
                    referrer_name = new_user_data.get('first_name', 'Новый пользователь')
                    welcome_msg = (
                        f"🎉 <b>Новый реферал!</b>\n\n"
                        f"По твоей ссылке присоединился {referrer_name}!\n"
                        f"Когда он оплатит подписку - ты получишь бонус!"
                    )
                    await bot.send_message(referrer_id, welcome_msg)
                except Exception as e:
                    logger.error(f"⚠️ Не удалось уведомить реферера {referrer_id}: {e}")
        
        # ========== ОТПРАВЛЯЕМ ПРИВЕТСТВИЕ И ПЕРВОЕ ЗАДАНИЕ ==========
        
        # Приветствие в зависимости от архетипа
        if archetype == "spartan":
            welcome_message = (
                "🎯 <b>ПУТЬ СПАРТАНЦА ВЫБРАН</b>\n\n"
            )
        else:
            welcome_message = (
                "🎯 <b>ПУТЬ АМАЗОНКИ ВЫБРАН</b>\n\n"
            )
        
        # Получаем первое задание
        try:
            task_id, task = await utils.get_task_by_day(1, archetype)
            
            if task:
                gender_ending = "ТВОЕ" if archetype == "spartan" else "ТВОЁ"
                
                task_message = (
                    f"{welcome_message}"
                    f"<b>{gender_ending} ПЕРВОЕ ЗАДАНИЕ!</b>\n\n"
                    f"<b>День 1/300</b>\n\n"
                    f"{task['text']}\n\n"
                    f"⏰ Выполни задание до 23:59\n\n"
                    f"<i>Отмечай выполнение кнопками 👇</i>"
                )
                
                await message.answer(
                    task_message,
                    reply_markup=keyboards.task_keyboard,
                    disable_web_page_preview=True
                )
                
                # Обновляем данные пользователя
                new_user_data['last_task_sent'] = datetime.now().isoformat()
                new_user_data['task_completed_today'] = False
                await utils.save_user(user_id, new_user_data)
                
                logger.info(f"✅ Первое задание отправлено пользователю {user_id}")
                
            else:
                # Если задание не найдено
                await message.answer(
                    f"{welcome_message}"
                    "К сожалению, первое задание временно недоступно.\n"
                    "Мы уже работаем над решением проблемы.\n\n"
                    "А пока можешь ознакомиться с функциями бота:",
                    reply_markup=keyboards.get_main_menu(user_id)
                )
                logger.warning(f"⚠️ Не найдено задание дня 1 для пользователя {user_id}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки задания: {e}")
            await message.answer(
                f"{welcome_message}"
                "Произошла ошибка при загрузке задания.\n"
                "Попробуй обновить меню через кнопку 'Задание на сегодня'.",
                reply_markup=keyboards.get_main_menu(user_id)
            )
        
        # Обновляем активность
        await utils.update_user_activity(user_id)
        
        # Очищаем состояние
        await state.clear()
        
        logger.info(f"✅ Регистрация пользователя {user_id} завершена успешно")
        
        # Уведомляем админа
        try:
            admin_message = (
                f"👤 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ</b>\n\n"
                f"📛 {user.first_name} (@{user.username or 'нет'})\n"
                f"🆔 {user_id}\n"
                f"🎯 Архетип: {'🛡️ Спартанец' if archetype == 'spartan' else '⚔️ Амазонка'}\n"
                f"🕐 Часовой пояс: {timezone}\n"
                f"🤝 Реферер: {referrer_id if referrer_id else 'нет'}"
            )
            await bot.send_message(config.ADMIN_ID, admin_message)
        except Exception as e:
            logger.error(f"⚠️ Не удалось уведомить админа: {e}")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в process_archetype: {e}", exc_info=True)
        try:
            await message.answer(
                "❌ <b>Произошла ошибка при регистрации</b>\n\n"
                "Пожалуйста, попробуй снова через /start"
            )
        except:
            pass
        await state.clear()
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
            "🔥 <b>Прекрасно! Ты становишься лучше!</b>",
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
            "🔥 <b>ЗАКАТНЫЙ РЫВОК!</b>\n\nПод закат солнца совершаются великие дела. Пусть сегодняшний вечер станет твоим триумфом!",
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
            "🔥 Настоящий рост происходит вне зоны комфорта.",
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
        f"⏰ <b>Выполни задание до 23:59</b>\n\n"
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
@dp.message(F.text == "Сертификаты 🎁")
async def show_certificates_menu(message: Message):
    """Показывает меню сертификатов"""
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    message_text = (
        "<b>СЕРТИФИКАТЫ 🎁</b>\n\n"
        "🎁 <b>Купить подарочный сертификат</b> - подарить подписку другу с красивым сертификатом спартанца\n\n"
        "🎫 <b>Активировать инвайт-код</b> - если у тебя есть код активации или сертификат\n\n"
        "Выбери действие:"
    )
    
    # Используем существующую клавиатуру для инвайт-кодов
    from keyboards import get_invite_codes_keyboard
    await message.answer(message_text, reply_markup=get_invite_codes_keyboard())
# НОВЫЙ обработчик подарка подписки
@dp.callback_query(F.data == "gift_subscription")
async def gift_subscription_handler(callback: CallbackQuery):
    """Подарок подписки другу - исправленная версия"""
    user = callback.from_user
    if not user:
        try:
            await callback.answer("❌ Ошибка пользователя")
        except:
            pass
        return
    
    if not callback.message:
        try:
            await callback.answer("❌ Ошибка: сообщение не найдено")
        except:
            pass
        return
    
    try:
        message_text = (
            "🎁 <b>ПОДАРОЧНЫЙ СЕРТИФИКАТ СПАРТАНЦА</b>\n\n"
            "💝 <b>Хотите сделать незабываемый подарок?</b>\n\n"
            "🎫 <b>Что вы получите:</b>\n"
            "1. Выбираете тариф подписки\n"
            "2. Оплачиваете через ЮKassa\n"
            "3. Получаете инвайт-код и красивый сертификат спартанца\n"
            "4. Сертификат можно распечатать для физического подарка\n"
            "5. Друг активирует подписку по QR-коду\n\n"
            "👥 <b>Преимущества сертификата:</b>\n"
            "• Подарочный код действует 30 дней\n"
            "• Красивый дизайн в стиле спартанца\n"
            "Выберите тариф для сертификата:"
        )
        
        # Используем обновленную клавиатуру для подарков
        from keyboards import get_gift_subscription_keyboard
        await callback.message.edit_text(
            message_text, 
            reply_markup=get_gift_subscription_keyboard()
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в gift_subscription_handler: {e}")
        try:
            await callback.answer("❌ Ошибка при загрузке тарифов")
        except:
            pass
    finally:
        try:
            await callback.answer()
        except:
            pass
# Добавить в bot.py после обработчика gift_subscription_handler
@dp.callback_query(F.data.startswith("gift_tariff_"))
async def process_gift_tariff_selection(callback: CallbackQuery):
    """Обработка выбора тарифа для подарка"""
    # БЕЗОПАСНАЯ ПРОВЕРКА ВСЕХ АТРИБУТОВ
    if not callback:
        return
    
    if not hasattr(callback, 'data') or not callback.data:
        try:
            await callback.answer("❌ Ошибка данных")
        except:
            pass
        return
    
    if not hasattr(callback, 'from_user') or not callback.from_user:
        try:
            await callback.answer("❌ Ошибка пользователя")
        except:
            pass
        return
    
    user = callback.from_user
    
    if not callback.message:
        try:
            await callback.answer("❌ Ошибка: сообщение не найдено")
        except:
            pass
        return
    
    # БЕЗОПАСНОЕ ИСПОЛЬЗОВАНИЕ replace
    try:
        callback_data = str(callback.data) if callback.data else ""
        tariff_id = callback_data.replace("gift_tariff_", "")
    except AttributeError:
        try:
            await callback.answer("❌ Ошибка обработки данных")
        except:
            pass
        return
    
    if not tariff_id:
        try:
            await callback.answer("❌ Неверный тариф")
        except:
            pass
        return
    
    # Проверяем, что tariff_id корректен
    if tariff_id not in ["month", "forever"]:
        try:
            await callback.answer(f"❌ Неизвестный тариф: {tariff_id}")
        except:
            pass
        return
    
    # Используем цены из config.TARIFFS
    base_tariff = config.TARIFFS.get(tariff_id)
    if not base_tariff:
        try:
            await callback.answer("❌ Тариф не найден")
        except:
            pass
        return
    
    # Создаем конфигурацию для подарка на основе основного тарифа
    gift_tariff = {
        "name": f"🎁 Подарочная {base_tariff['name'].lower()}",
        "price": base_tariff['price'],
        "days": base_tariff['days'],
        "type": f"gift_{tariff_id}"
    }
    
    try:
        # Создаем платеж в ЮKassa с пометкой что это подарок
        user_id = user.id
        description = f"{gift_tariff['name']} для пользователя {user.first_name or user.id}"
        
        payment_data = await payments.create_yookassa_payment(
            amount=gift_tariff['price'],
            description=description,
            user_id=user_id,
            tariff_id=f"gift_{tariff_id}"  # Добавляем префикс gift
        )
        
        if not payment_data:
            try:
                await callback.answer("❌ Ошибка создания платежа. Попробуйте позже.")
            except:
                pass
            return
        
        # Формируем сообщение об оплате подарка
        if tariff_id == "forever":
            message_text = (
                f"🎁 <b>ОПЛАТА ПОДАРОЧНОГО СЕРТИФИКАТА</b>\n\n"
                f"📦 <b>Тариф:</b> {gift_tariff['name']}\n"
                f"💰 <b>Сумма:</b> {gift_tariff['price']} руб.\n"
                f"♾️ <b>Срок:</b> НАВСЕГДА!\n\n"
                f"🎫 <b>После успешной оплаты:</b>\n"
                f"• Вы получите инвайт-код и красивый сертификат\n"
                f"• Сертификат можно распечатать для физического подарка\n"
                f"• QR-код для быстрой активации\n"
                f"• Пожизненный доступ к челленджу для друга\n\n"
            )
        else:
            message_text = (
                f"🎁 <b>ОПЛАТА ПОДАРОЧНОГО СЕРТИФИКАТА</b>\n\n"
                f"📦 <b>Тариф:</b> {gift_tariff['name']}\n"
                f"💰 <b>Сумма:</b> {gift_tariff['price']} руб.\n"
                f"⏰ <b>Срок:</b> {gift_tariff['days']} дней\n\n"
                f"🎫 <b>После успешной оплаты:</b>\n"
                f"• Вы получите инвайт-код и красивый сертификат\n"
                f"• Сертификат можно распечатать для физического подарка\n"
                f"• QR-код для быстрой активации\n"
                f"• Можно подарить любому человеку\n\n"
            )
        
        message_text += (
            f"🔗 <b>Ссылка для оплаты:</b>\n"
            f"<a href='{payment_data['confirmation_url']}'>Нажмите для перехода к оплате</a>\n\n"
            f"📱 <b>После оплаты:</b>\n"
            f"1. Вернитесь в бота\n"
            f"2. Нажмите кнопку «✅ Проверить оплату» ниже\n"
            f"3. Получите сертификат с QR-кодом для подарка\n\n"
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
                    callback_data=f"check_gift_payment_{payment_data['payment_id']}"
                )],
                [InlineKeyboardButton(
                    text="🔄 Обновить страницу оплаты", 
                    callback_data=f"refresh_gift_payment_{payment_data['payment_id']}"
                )],
                [InlineKeyboardButton(
                    text="🔙 Назад к выбору подарка", 
                    callback_data="gift_subscription"
                )]
            ]
        )
        
        try:
            await callback.message.edit_text(message_text, reply_markup=keyboard)
            await callback.answer("✅ Платеж создан! Перейдите по ссылке для оплаты.")
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            try:
                await callback.answer("❌ Не удалось обновить сообщение")
            except:
                pass
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания платежа для подарка: {e}")
        try:
            await callback.answer("❌ Ошибка при создании платежа")
        except:
            pass
# Добавить в bot.py
@dp.callback_query(F.data.startswith("check_gift_payment_"))
async def check_gift_payment_handler(callback: CallbackQuery):
    """Проверка статуса оплаты подарка"""
    # БЕЗОПАСНАЯ ПРОВЕРКА ВСЕХ ВОЗМОЖНЫХ None
    if not callback or not callback.data:
        try:
            await callback.answer("❌ Ошибка данных")
        except:
            pass
        return
    
    # Безопасное получение payment_id
    try:
        payment_id = str(callback.data).replace("check_gift_payment_", "") if callback.data else ""
    except AttributeError:
        payment_id = ""
    
    if not payment_id:
        try:
            await callback.answer("❌ ID платежа не найден")
        except:
            pass
        return
    
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
        
        if payment_data.get('user_id') != user.id:
            await safe_edit_message(callback, "❌ Это не ваш платеж")
            return
        
        if payment_status == "succeeded":
            # Обрабатываем успешную оплату подарка
            await activate_gift_subscription(payment_data, callback)
            
        elif payment_status == "pending":
            check_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔄 Проверить еще раз", 
                    callback_data=f"check_gift_payment_{payment_id}"
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
            from keyboards import get_gift_subscription_keyboard
            await safe_edit_message(
                callback,
                "❌ <b>Платеж отменен</b>\n\n"
                "Вы можете создать новый платеж или выбрать другой тариф.",
                get_gift_subscription_keyboard()
            )
            
        elif payment_status is None:
            check_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔄 Попробовать снова", 
                    callback_data=f"check_gift_payment_{payment_id}"
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
                    callback_data=f"check_gift_payment_{payment_id}"
                )
            ]])
            
            await safe_edit_message(
                callback,
                f"📊 <b>Статус платежа:</b> {payment_status}\n\n"
                "Продолжайте ожидание или попробуйте проверить позже.",
                check_keyboard
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки платежа подарка: {e}")
        await safe_edit_message(
            callback,
            "❌ <b>Произошла ошибка при проверке платежа</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку."
        )
# Добавить в bot.py
async def activate_gift_subscription(payment_data, callback):
    """Активация подарка после успешной оплаты с красивым сертификатом спартанца"""
    if not callback:
        logger.error("❌ activate_gift_subscription: callback is None")
        return
    
    # Безопасное получение данных
    user_id = payment_data.get('user_id')
    tariff_id = payment_data.get('tariff_id', '')
    
    if not user_id:
        logger.error("❌ activate_gift_subscription: user_id is None")
        await safe_edit_message(callback, "❌ Ошибка: не найден ID пользователя")
        return
    
    # Определяем тип подарка и берем данные из config.TARIFFS
    base_tariff_id = tariff_id.replace("gift_", "")
    base_tariff = config.TARIFFS.get(base_tariff_id)
    
    if base_tariff:
        tariff = {
            "name": f"🎁 Подарочная {base_tariff['name'].lower()}",
            "days": base_tariff['days'],
            "price": base_tariff['price']
        }
        # Определяем тип подписки
        subscription_type = 'forever' if base_tariff_id == 'forever' else 'month'
    else:
        # По умолчанию месячная
        tariff = {
            "name": "🎁 Подарочная подписка",
            "days": 30,
            "price": payment_data.get('amount', 0)
        }
        subscription_type = 'month'
    
    try:
        # ОБНОВЛЯЕМ статус платежа
        await payments.update_payment_status(payment_data['payment_id'], 'succeeded')
        
        # Определяем тип кода для подарка
        code_type = f"gift_{subscription_type}"
        
        # Создаем инвайт-код для подарка
        invite_code = await utils.create_invite_code(
            code_type=code_type,
            days=tariff['days'],
            max_uses=1,
            created_by=user_id,
            is_gift=True,
            extra_data={
                "subscription_type": subscription_type,
                "is_forever": subscription_type == 'forever'
            }
        )
        
        if not invite_code:
            raise Exception("Не удалось создать инвайт-код")
        
        # СОЗДАЕМ СЕРТИФИКАТ СПАРТАНЦА
        try:
            import os
            from aiogram.types import FSInputFile
            
            # Проверяем существует ли модуль сертификатов
            try:
                from certificates.spartan_generator import spartan_certificate_generator
                generator_available = True
            except ImportError:
                logger.warning("⚠️ Модуль certificates.spartan_generator не найден")
                generator_available = False
            
            if generator_available:
                # Получаем данные покупателя
                buyer_name = callback.from_user.first_name if callback.from_user else "Покупатель"
                buyer_username = callback.from_user.username if callback.from_user else None
                
                buyer_data = {
                    'first_name': buyer_name,
                    'username': buyer_username,
                    'user_id': user_id
                }
                
                html_content = spartan_certificate_generator.generate_certificate(
                    invite_code=invite_code,
                    tariff_data=tariff,
                    buyer_data=buyer_data,
                    config=config
                )
                
                # Сохраняем файл
                filepath = spartan_certificate_generator.save_certificate(invite_code, html_content)
                
                if filepath and os.path.exists(filepath):
                    logger.info(f"✅ Спартанский сертификат создан: {filepath}")
                    
                    # Отправляем единое сообщение с кодом и сертификатом
                    certificate_file = FSInputFile(filepath)
                    
                    if subscription_type == 'forever':
                        combined_message = (
                            f"🎉 <b>ПОДАРОК ОПЛАЧЕН!</b>\n\n"
                            f"💝 <b>Поздравляем с покупкой пожизненного сертификата!</b>\n\n"
                            f"🎫 <b>Инвайт-код для подарка:</b>\n"
                            f"<code>{invite_code}</code>\n\n"
                            f"♾️ <b>Тип подписки:</b> ПОЖИЗНЕННАЯ\n"
                            f"📄 Подарочный сертификат прикреплён к сообщению.\n"
                            f"Его можно распечатать и подарить физически.\n\n"
                        )
                    else:
                        combined_message = (
                            f"🎉 <b>ПОДАРОК ОПЛАЧЕН!</b>\n\n"
                            f"💝 <b>Поздравляем с покупкой!</b>\n\n"
                            f"🎫 <b>Инвайт-код для подарка:</b>\n"
                            f"<code>{invite_code}</code>\n\n"
                            f"📄 Подарочный сертификат прикреплён к сообщению.\n"
                            f"Его можно распечатать и подарить физически.\n\n"
                        )
                    
                    combined_message += (
                        f"📝 <b>Как подарить:</b>\n"
                        f"1. Отправьте код или сертификат другу\n"
                        f"2. Он переходит в бота @{config.BOT_USERNAME}\n"
                        f"3. Нажимает START для регистрации\n"
                        f"4. Выбирает «Сертификаты 🎁» → «🎫 Активировать инвайт-код»\n"
                        f"5. Вводит код \n\n"
                        f"⚠️ <b>Важно:</b>\n"
                        f"• Код можно использовать только 1 раз\n"
                        f"• Действителен 30 дней\n"
                    )
                    
                    # Отправляем сообщение с документом
                    await bot.send_document(
                        chat_id=user_id,
                        document=certificate_file,
                        caption=combined_message,
                        parse_mode="HTML"
                    )
                    
                    # Удаляем временный файл через 60 секунд
                    await asyncio.sleep(60)
                    try:
                        os.remove(filepath)
                        logger.info(f"🗑️ Временный файл удален: {filepath}")
                    except Exception as delete_error:
                        logger.error(f"Ошибка удаления файла {filepath}: {delete_error}")
                else:
                    logger.error("❌ Не удалось создать файл сертификата")
                    generator_available = False
            else:
                logger.warning("⚠️ Генератор сертификатов недоступен, отправляем только код")
                generator_available = False
                
        except Exception as cert_error:
            logger.error(f"❌ Ошибка создания сертификата: {cert_error}", exc_info=True)
            generator_available = False
        
        # Если генератор сертификатов недоступен, отправляем только код
        if not generator_available:
            if subscription_type == 'forever':
                fallback_message = (
                    f"🎉 <b>ПОДАРОК ОПЛАЧЕН!</b>\n\n"
                    f"💝 <b>Поздравляем с покупкой пожизненного сертификата!</b>\n\n"
                    f"🎫 <b>Инвайт-код для подарка:</b>\n"
                    f"<code>{invite_code}</code>\n\n"
                    f"♾️ <b>Тип подписки:</b> ПОЖИЗНЕННАЯ\n\n"
                )
            else:
                fallback_message = (
                    f"🎉 <b>ПОДАРОК ОПЛАЧЕН!</b>\n\n"
                    f"💝 <b>Поздравляем с покупкой!</b>\n\n"
                    f"🎫 <b>Инвайт-код для подарка:</b>\n"
                    f"<code>{invite_code}</code>\n\n"
                )
            
            fallback_message += (
                f"📝 <b>Как подарить:</b>\n"
                f"1. Отправьте этот код другу\n"
                f"2. Он должен перейти в бота @{config.BOT_USERNAME}\n"
                f"3. Нажать START для регистрации\n"
                f"4. Затем выбрать «Сертификаты 🎁» → «🎫 Активировать инвайт-код»\n"
                f"5. Ввести код и активировать подписку\n\n"
                f"⚠️ <b>Внимание:</b>\n"
                f"• Код можно использовать только 1 раз!\n"
                f"• Действителен 30 дней\n"
                f"• Можно подарить любому человеку"
            )
            
            # Отправляем сообщение с кодом
            await bot.send_message(
                chat_id=user_id,
                text=fallback_message,
                parse_mode="HTML"
            )
        
        # Редактируем оригинальное сообщение
        await safe_edit_message(callback, "✅ Подарок успешно создан! Проверьте сообщения от бота.")
        
        # УВЕДОМЛЯЕМ админа о подарке
        try:
            buyer_name = callback.from_user.first_name if callback.from_user else "Покупатель"
            buyer_username = f"@{callback.from_user.username}" if callback.from_user and callback.from_user.username else "нет"
            
            admin_message = (
                f"🎁 <b>НОВЫЙ ПОДАРОК</b>\n\n"
                f"👤 {buyer_name} ({buyer_username})\n"
                f"🆔 {user_id}\n"
                f"💎 {tariff['name']}\n"
                f"💰 {tariff['price']} руб.\n"
                f"{'♾️ Тип: Пожизненный' if subscription_type == 'forever' else '📅 Тип: Месячный'}\n"
                f"🎫 Код: {invite_code}"
            )
            await bot.send_message(config.ADMIN_ID, admin_message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка уведомления админа: {e}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания подарка: {e}", exc_info=True)
        error_message = (
            f"❌ <b>Произошла ошибка при создании подарка</b>\n\n"
            f"Платеж прошел успешно, но не удалось создать инвайт-код.\n"
            f"Обратитесь в поддержку: @{config.SUPPORT_USERNAME}\n\n"
            f"При обращении укажите ID платежа:\n"
            f"<code>{payment_data['payment_id']}</code>"
        )
        await safe_edit_message(callback, error_message)
# Добавить в bot.py
@dp.callback_query(F.data.startswith("refresh_gift_payment_"))
async def refresh_gift_payment_handler(callback: CallbackQuery):
    """Обновление страницы оплаты подарка"""
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
        
    try:
        payment_id = str(callback.data).replace("refresh_gift_payment_", "") if callback.data else ""
    except AttributeError:
        payment_id = ""
    
    payment_data = await payments.get_payment_data(payment_id)
    
    if payment_data:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔗 Перейти к оплате", 
                url=payment_data['confirmation_url']
            )],
            [InlineKeyboardButton(
                text="✅ Проверить оплату", 
                callback_data=f"check_gift_payment_{payment_data['payment_id']}"
            )]
        ])
        
        success = await safe_edit_reply_markup(callback, keyboard)
        if success:
            await callback.answer("✅ Ссылка обновлена")
        else:
            await callback.answer("❌ Ошибка обновления")
    else:
        await callback.answer("❌ Платеж не найден")
# Добавить в bot.py
@dp.callback_query(F.data == "back_to_invite_codes")
async def back_to_invite_codes_handler(callback: CallbackQuery):
    """Возврат к разделу инвайт-кодов"""
    if not callback or not callback.message:
        return
    
    user = callback.from_user
    if not user:
        try:
            await callback.answer("❌ Ошибка пользователя")
        except:
            pass
        return
    
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        try:
            await callback.answer("Сначала зарегистрируйся через /start")
        except:
            pass
        return
    
    message_text = (
        "<b>ИНВАЙТ-КОДЫ 💌</b>\n\n"
        "🎫 <b>Активировать инвайт-код</b> - если у тебя есть код активации\n\n"
        "🎁 <b>Подарить подписку другу</b> - купить доступ в подарок\n\n"
        "Выбери действие:"
    )
    
    # Используем существующую клавиатуру для инвайт-кодов
    from keyboards import get_invite_codes_keyboard
    await callback.message.edit_text(message_text, reply_markup=get_invite_codes_keyboard())
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
# В обработчике task_completed обновляем логику (уже есть в коде):

@dp.message(F.text == "✅ ГОТОВО")
async def task_completed(message: Message):
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        return
    
    # 🔥 Сбрасываем флаг блокировки за вчерашнее задание
    if user_data.get('needs_to_complete_yesterday', False):
        user_data['needs_to_complete_yesterday'] = False
        logger.info(f"✅ Сброшен флаг needs_to_complete_yesterday для пользователя {user_id}")
    
    # Сохраняем старый ранг для сравнения
    old_rank = user_data.get('rank', 'putnik')
    
    # Получаем гендерные окончания - БЕЗОПАСНАЯ ВЕРСИЯ
    try:
        gender = await utils.get_gender_ending(user_data)
        # Проверяем наличие ключей
        if 'verb_finished' not in gender:
            gender['verb_finished'] = 'завершил' if user_data.get('archetype', 'spartan') == 'spartan' else 'завершила'
        if 'ending_a' not in gender:
            gender['ending_a'] = '' if user_data.get('archetype', 'spartan') == 'spartan' else 'а'
        if 'ending' not in gender:
            gender['ending'] = '' if user_data.get('archetype', 'spartan') == 'spartan' else 'а'
        if 'ending_te' not in gender:
            gender['ending_te'] = '' if user_data.get('archetype', 'spartan') == 'spartan' else 'а'
    except Exception as e:
        logger.error(f"❌ Ошибка получения гендерных окончаний: {e}")
        # Значения по умолчанию
        gender = {
            'verb_finished': 'завершил',
            'ending_a': '',
            'ending': '',
            'ending_te': ''
        }
    
    # Проверяем текущие задания
    todays_tasks = await utils.get_todays_tasks(user_data)
    
    if not todays_tasks:
        await message.answer("❌ Нет активных заданий!")
        return
    
    # Обновляем прогресс
    user_data['current_day'] = user_data.get('current_day', 0) + 1
    user_data['completed_tasks'] = user_data.get('completed_tasks', 0) + 1
    user_data['task_completed_today'] = True
    
    # Проверяем пробный период
    in_trial = await utils.is_in_trial_period(user_data)
    
    # Если в пробном периоде - увеличиваем счетчик
    if in_trial:
        trial_tasks = user_data.get('completed_tasks_in_trial', 0)
        new_trial_count = trial_tasks + 1
        
        logger.info(f"📊 Пробный период: было {trial_tasks} заданий, станет {new_trial_count}")
        
        # Обновляем счетчик
        user_data['completed_tasks_in_trial'] = new_trial_count
        
        # Проверяем, закончился ли пробный период (3 задания) - только для информации
        # Но фактическое завершение пробного периода теперь через 3 дня с регистрации
        if new_trial_count >= 3:
            user_data['trial_finished'] = True
            logger.info(f"🎯 Пользователь {user_id} выполнил 3 задания в пробном периоде")
    
    # Обновляем ранг и получаем результат
    rank_updated = await utils.update_user_rank(user_data)
    new_rank = user_data.get('rank', 'putnik')
    
    await utils.save_user(user_id, user_data)
    
    # 🔥 ОТПРАВЛЯЕМ КРАСИВОЕ УВЕДОМЛЕНИЕ О РАНГЕ (если ранг изменился)
    if rank_updated and old_rank != new_rank:
        # Отправляем красивое уведомление о ранге
        await RankNotifications.send_rank_up_notification(bot, user_id, old_rank, new_rank, user_data)
        
        # Также уведомляем админа
        try:
            admin_message = (
                f"🏆 <b>Пользователь повысил ранг!</b>\n\n"
                f"👤 {user.first_name} (@{user.username or 'нет'})\n"
                f"🆔 {user_id}\n"
                f"📈 {old_rank} → {new_rank}\n"
                f"✅ Выполнено: {user_data.get('completed_tasks', 0)} заданий"
            )
            await bot.send_message(config.ADMIN_ID, admin_message)
        except Exception as e:
            logger.error(f"Ошибка уведомления админа о ранге: {e}")
    
    # Получаем базовое сообщение о выполнении задания (без упоминания ранга)
    reply = await BotReplies.get_task_completed_reply(gender, rank_updated, "")
    
    await message.answer(
        reply,
        reply_markup=keyboards.get_main_menu(user_id)
    )
    
    # ⚠️ УДАЛЕНО: НЕ отправляем уведомление о завершении пробного периода здесь
    # Теперь это делает автоматическая система уведомлений SubscriptionNotifications
    # которая проверяет всех пользователей ежедневно в 11:00
    
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
            # Проверяем, пожизненная ли подписка
            if user_data.get('subscription_type') == 'forever':
                message_text += "♾️ <b>Статус:</b> ПОЖИЗНЕННАЯ ПОДПИСКА\n"
                message_text += "✅ Доступ навсегда\n\n"
            else:
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
        
        # ПОКАЗЫВАЕМ ТОЛЬКО ПЛАТНЫЕ ТАРИФЫ
        for tariff_id, tariff in config.TARIFFS.items():
            if tariff_id == 'month':
                message_text += f"• {tariff['name']} - {tariff['price']} руб. (30 дней)\n"
            elif tariff_id == 'forever':
                message_text += f"• {tariff['name']} - {tariff['price']} руб. (навсегда)\n"
        
        await message.answer(message_text, reply_markup=keyboards.get_payment_keyboard())
        
    except Exception as e:
        logger.error(f"❌ Ошибка в show_subscription: {e}")
        await message.answer("❌ Произошла ошибка при загрузке информации о подписке")
@dp.message(F.text == "⏭️ ПРОПУСТИТЬ")
async def skip_task(message: Message):
    user = message.from_user
    if not user:
        return
        
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    # 🔥 Сбрасываем флаг блокировки за вчерашнее задание
    if user_data.get('needs_to_complete_yesterday', False):
        user_data['needs_to_complete_yesterday'] = False
        logger.info(f"✅ Сброшен флаг needs_to_complete_yesterday (пропуск) для пользователя {user_id}")
    
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
    
    # Проверяем пробный период
    in_trial = await utils.is_in_trial_period(user_data)
    
    # Если в пробном периоде - увеличиваем счетчик
    if in_trial:
        trial_tasks = user_data.get('completed_tasks_in_trial', 0)
        new_trial_count = trial_tasks + 1
        
        logger.info(f"📊 Пропуск в пробном периоде: было {trial_tasks}, станет {new_trial_count}")
        
        user_data['completed_tasks_in_trial'] = new_trial_count
        
        if new_trial_count >= 3:
            user_data['trial_finished'] = True
            logger.info(f"🎯 Пробный период завершен (пропуском) для пользователя {user_id}")
    
    await utils.save_user(user_id, user_data)
    
    # Получаем случайную реплику
    reply = await BotReplies.get_task_skipped_reply(gender)
    
    await message.answer(
        reply,
        reply_markup=keyboards.get_main_menu(user_id)
    )
    
    await utils.update_user_activity(user_id)

# НАЙДИТЕ ЭТОТ ОБРАБОТЧИК И ОБНОВИТЕ ЕГО:
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
    
    # Проверяем, действительно ли пробный период закончился
    in_trial = await utils.is_in_trial_period(user_data)
    trial_tasks = user_data.get('completed_tasks_in_trial', 0)
    
    # Если пробный период еще активен, информируем пользователя
    if in_trial and trial_tasks < 3:
        message_text = (
            f"ℹ️ <b>Твой пробный период еще активен!</b>\n\n"
            f"Осталось заданий: {3 - trial_tasks}\n"
            f"Заверши пробный период, чтобы получить полное представление о системе.\n\n"
            f"А пока можешь ознакомиться с тарифами:"
        )
    else:
        # Показываем тарифы для оплаты
        message_text = (
            "💎 <b>АКТИВАЦИЯ ПОДПИСКИ</b>\n\n"
            "Пробный период завершен. Выберите тариф для продолжения:\n\n"
            "📅 <b>Месячная подписка</b> - 300 руб.\n"
            "♾️ <b>Пожизненная подписка</b> - 1990 руб. (навсегда!)\n\n"
            "<b>После оплаты задание придет сразу же!</b> ⚡"
        )
    
    try:
        await callback.message.edit_text(message_text, reply_markup=keyboards.get_payment_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        try:
            await callback.message.answer(message_text, reply_markup=keyboards.get_payment_keyboard())
        except Exception as e2:
            logger.error(f"Ошибка при отправке сообщения: {e2}")
    
    await callback.answer()
# НОВЫЙ обработчик "Инвайт-коды 💌"
@dp.callback_query(F.data == "back_to_certificates")
async def back_to_certificates_handler(callback: CallbackQuery):
    """Возврат к разделу сертификатов"""
    if not callback or not callback.message:
        return
    
    user = callback.from_user
    if not user:
        try:
            await callback.answer("❌ Ошибка пользователя")
        except:
            pass
        return
    
    user_id = user.id
    user_data = await utils.get_user(user_id)
    
    if not user_data:
        try:
            await callback.answer("Сначала зарегистрируйся через /start")
        except:
            pass
        return
    
    message_text = (
        "<b>СЕРТИФИКАТЫ 🎁</b>\n\n"
        "🎁 <b>Купить подарочный сертификат</b> - подарить подписку другу с красивым сертификатом спартанца\n\n"
        "🎫 <b>Активировать инвайт-код</b> - если у тебя есть код активации или сертификат\n\n"
        "Выбери действие:"
    )
    
    # Используем существующую клавиатуру для инвайт-кодов
    await callback.message.edit_text(message_text, reply_markup=keyboards.get_invite_codes_keyboard())
    await callback.answer()

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


# Обновите функцию process_tariff_selection в bot.py:

@dp.callback_query(F.data.startswith("tariff_"))
async def process_tariff_selection(callback: CallbackQuery):
    """Обработка выбора тарифа"""
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
        if tariff_id == "forever":
            message_text = (
                f"<b>♾️ ОПЛАТА ПОЖИЗНЕННОЙ ПОДПИСКИ</b>\n\n"
                f"📦 <b>Тариф:</b> {tariff['name']}\n"
                f"💰 <b>Сумма:</b> {tariff['price']} руб.\n"
                f"⏰ <b>Срок:</b> НАВСЕГДА!\n\n"
                f"🎁 <b>Преимущества:</b>\n"
                f"• Доступ ко всем заданиям навсегда\n"
                f"• Возможность проходить челлендж в удобном темпе\n\n"
            )
        else:
            message_text = (
                f"<b>💎 ОПЛАТА ПОДПИСКИ</b>\n\n"
                f"📦 <b>Тариф:</b> {tariff['name']}\n"
                f"💰 <b>Сумма:</b> {tariff['price']} руб.\n"
                f"⏰ <b>Срок:</b> {tariff['days']} дней\n\n"
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
    """Активация подписки после успешной оплаты с реферальным начислением"""
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
    
    # ОСОБАЯ ЛОГИКА ДЛЯ ПОЖИЗНЕННОЙ ПОДПИСКИ
    if tariff_id == "forever":
        # Добавляем 100 лет (фактически навсегда)
        updated_user_data = await utils.add_subscription_days(user_data, 36500)
        # Помечаем как пожизненную
        updated_user_data['subscription_type'] = 'forever'
        subscription_message = "Пожизненная подписка активирована навсегда!"
    else:
        # Обычная месячная подписка
        updated_user_data = await utils.add_subscription_days(user_data, tariff['days'])
        subscription_message = f"Подписка активирована на {tariff['days']} дней!"
    
    # Начисляем реферальный бонус
    referral_result = await utils.process_referral_payment(
        user_id, 
        tariff['price'], 
        tariff_id
    )
    
    # Обработка реферального результата
    if referral_result and len(referral_result) == 4:
        success, referrer_id, bonus_amount, percent = referral_result
        
        if success and referrer_id and bonus_amount > 0:
            referrer_data = await utils.get_user(referrer_id)
            new_balance = referrer_data.get('referral_earnings', 0) if referrer_data else 0
            
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
    
    await utils.save_user(user_id, updated_user_data)
    
    success_message = (
        f"✅ <b>Подписка активирована!</b>\n\n"
        f"💎 Тариф: {tariff['name']}\n"
        f"{'⏰ Срок: ' + tariff['description'] if tariff_id != 'forever' else '♾️ Срок: навсегда'}\n"
        f"💰 Стоимость: {tariff['price']} руб.\n"
        f"🎯 {subscription_message}\n\n"
    )
    
    if success and bonus_amount > 0:
        success_message += f"🎉 <b>Вы принесли доход своему рефереру: {bonus_amount} руб.!</b>\n\n"
    
    success_message += f"Задания будут приходить ежедневно в 9:00 🕘\n\n"
    success_message += "<b>Твое следующее задание придет прямо сейчас! ⬇️</b>"
    
    success_edit = await safe_edit_message(callback, success_message)
    if not success_edit:
        await safe_send_message(user_id, success_message)
    
    # Отправляем задание немедленно
    try:
        current_day = updated_user_data.get('current_day', 0)
        next_day = current_day + 1
        
        if next_day == 0:
            next_day = 1
            
        task_id, task = await utils.get_task_by_day(next_day, updated_user_data.get('archetype', 'spartan'))
        
        if task:
            task_message = (
                f"📋 <b>Новое задание!</b>\n\n"
                f"<b>День {next_day}/300</b>\n\n"
                f"{task['text']}\n\n"
                f"⏰ <b>Выполни задание до 23:59</b>\n\n"
                f"<i>Отмечай выполнение кнопками ниже 👇</i>"
            )
            
            await bot.send_message(
                chat_id=user_id,
                text=task_message,
                reply_markup=keyboards.task_keyboard,
                disable_web_page_preview=True
            )
            
            updated_user_data['last_task_sent'] = datetime.now().isoformat()
            updated_user_data['task_completed_today'] = False
            await utils.save_user(user_id, updated_user_data)
            
            logger.info(f"✅ Задание дня {next_day} отправлено пользователю {user_id} после активации подписки")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки задания после активации подписки пользователю {user_id}: {e}")
    
    # Уведомление админа
    try:
        user = callback.from_user
        if user:
            admin_message = (
                f"🎉 <b>Новая подписка активирована!</b>\n\n"
                f"👤 Пользователь: {user.first_name} (@{user.username or 'нет'})\n"
                f"🆔 ID: {user_id}\n"
                f"💎 Тариф: {tariff['name']}\n"
                f"💰 Сумма: {tariff['price']} руб.\n"
                f"{'♾️ Тип: Пожизненная' if tariff_id == 'forever' else f'📅 Дней: {tariff['days']}'}\n"
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


# ========== СЕРТИФИКАТЫ ==========

@dp.message(F.text == "🎁 Создать сертификат")
async def admin_create_certificate_start(message: Message, state: FSMContext):
    """Начало создания сертификата - УПРОЩЕННАЯ ВЕРСИЯ"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    await message.answer(
        "🎁 <b>СОЗДАНИЕ СЕРТИФИКАТА</b>\n\n"
        "Выберите тип сертификата:\n\n"
        "📅 <b>Месячный (30 дней)</b> - стандартная подписка\n"
        "📆 <b>Годовой (365 дней)</b> - премиальная подписка\n\n"
        "Сертификат будет <b>общим</b> - его можно подарить любому пользователю!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📅 Месячный (30 дней)", callback_data="certificate_month")],
                [InlineKeyboardButton(text="📆 Годовой (365 дней)", callback_data="certificate_year")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="certificate_cancel")]
            ]
        )
    )
    await state.set_state(UserStates.admin_waiting_certificate_type)

@dp.callback_query(UserStates.admin_waiting_certificate_type, F.data.startswith("certificate_"))
async def admin_certificate_type_selected(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа сертификата - УПРОЩЕННАЯ"""
    if not callback or not callback.message or not callback.from_user:
        return
    
    user = callback.from_user
    if user.id != config.ADMIN_ID:
        try:
            await callback.answer("⛔ Нет доступа")
        except:
            pass
        return
    
    certificate_type = callback.data
    
    if certificate_type == "certificate_cancel":
        try:
            if callback.message:
                await callback.message.edit_text("❌ Создание сертификата отменено")
        except:
            try:
                if callback.message:
                    await callback.message.answer("❌ Создание сертификата отменено")
            except:
                pass
        await state.clear()
        try:
            await callback.answer()
        except:
            pass
        return
    
    # Определяем параметры
    if certificate_type == "certificate_month":
        days = 30
        certificate_name = "📅 Месячный сертификат"
        code_type = "certificate_month"
    elif certificate_type == "certificate_year":
        days = 365
        certificate_name = "📆 Годовой сертификат"
        code_type = "certificate_year"
    else:
        days = 30
        certificate_name = "Сертификат"
        code_type = "certificate_month"
    
    # Сразу создаем сертификат
    await create_simple_certificate(
        callback=callback,
        state=state,
        certificate_name=certificate_name,
        days=days,
        code_type=code_type,
        admin_id=user.id,
        admin_name=user.first_name or "Администратор"
    )
async def create_simple_certificate(callback: CallbackQuery, state: FSMContext, 
                                   certificate_name: str, days: int, 
                                   code_type: str, admin_id: int, admin_name: str):
    """Создание простого сертификата (общего)"""
    try:
        # Проверяем что callback и message существуют
        if not callback or not callback.message:
            return
        
        # Создаем инвайт-код для сертификата
        invite_code = await utils.create_invite_code(
            code_type=code_type,
            days=days,
            max_uses=1,
            created_by=admin_id,
            is_gift=True,
            extra_data={
                "is_certificate": True,
                "certificate_name": certificate_name,
                "certificate_days": days,
                "created_by_admin": True,
                "admin_id": admin_id,
                "created_at": datetime.now().isoformat(),
                "recipient_info": "Общий сертификат (можно подарить любому)",
                "is_active": True
            }
        )
        
        if not invite_code:
            try:
                await callback.message.edit_text(
                    "❌ <b>ОШИБКА СОЗДАНИЯ СЕРТИФИКАТА</b>\n\n"
                    "Не удалось создать инвайт-код. Попробуйте снова."
                )
            except:
                await callback.message.answer(
                    "❌ <b>ОШИБКА СОЗДАНИЯ СЕРТИФИКАТА</b>\n\n"
                    "Не удалось создать инвайт-код. Попробуйте снова."
                )
            await state.clear()
            try:
                await callback.answer()
            except:
                pass
            return
        
        # Формируем сообщение с результатом
        result_message = (
            f"✅ <b>СЕРТИФИКАТ СОЗДАН!</b>\n\n"
            f"🎁 <b>Тип:</b> {certificate_name}\n"
            f"⏰ <b>Срок:</b> {days} дней\n"
            f"👤 <b>Для кого:</b> Общий сертификат (можно подарить любому)\n"
            f"🎫 <b>Код активации:</b>\n"
            f"<code>{invite_code}</code>\n\n"
            f"📋 <b>ИНСТРУКЦИЯ:</b>\n"
            f"1. Отправьте код любому человеку\n"
            f"2. Он должен зайти в раздел «Сертификаты 🎁»\n"
            f"3. Нажать «🎫 Активировать инвайт-код»\n"
            f"4. Ввести код и активировать подписку\n\n"
            f"⏰ <b>Сертификат действует 90 дней</b>\n"
            f"👤 <b>Создал:</b> {admin_name}"
        )
        
        # Пытаемся создать файл сертификата
        file_created = False
        try:
            from certificates.spartan_generator import spartan_certificate_generator
            
            # Данные для сертификата
            certificate_data = {
                'invite_code': invite_code,
                'tariff_data': {
                    'name': certificate_name,
                    'days': days,
                    'price': 0
                },
                'buyer_data': {
                    'first_name': admin_name,
                    'username': callback.from_user.username if callback.from_user else None,
                    'user_id': admin_id
                },
                'recipient_info': "Общий сертификат",
                'created_at': datetime.now().strftime("%d.%m.%Y")
            }
            
            # Генерируем HTML контент
            html_content = spartan_certificate_generator.generate_certificate(
                invite_code=invite_code,
                tariff_data=certificate_data['tariff_data'],
                buyer_data=certificate_data['buyer_data'],
                config=config
            )
            
            # Сохраняем файл
            filepath = spartan_certificate_generator.save_certificate(f"cert_{invite_code}", html_content)
            
            # Отправляем файл
            from aiogram.types import FSInputFile
            certificate_file = FSInputFile(filepath)
            
            # Отправляем файл отдельным сообщением
            await callback.message.answer_document(
                certificate_file,
                caption=f"📄 <b>Файл сертификата</b>\nКод: <code>{invite_code}</code>"
            )
            
            result_message += f"\n\n📄 <b>Файл сертификата отправлен отдельным сообщением</b>"
            file_created = True
            
            # Удаляем временный файл
            await asyncio.sleep(30)
            try:
                import os
                os.remove(filepath)
                logger.info(f"🗑️ Временный файл удален: {filepath}")
            except Exception as delete_error:
                logger.error(f"Ошибка удаления файла: {delete_error}")
                
        except ImportError:
            logger.warning("Модуль генерации сертификатов не найден")
            result_message += f"\n\n⚠️ <i>Файл сертификата не создан (модуль не найден)</i>"
        except Exception as cert_error:
            logger.error(f"Ошибка создания файла сертификата: {cert_error}")
            result_message += f"\n\n⚠️ <i>Файл сертификата не создан (ошибка)</i>"
        
        # Отправляем результат
        try:
            await callback.message.edit_text(result_message, parse_mode="HTML")
        except:
            try:
                await callback.message.answer(result_message, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Ошибка отправки результата: {e}")
        
        # Логируем создание
        logger.info(f"🎁 Сертификат создан: {certificate_name}, код: {invite_code}, дней: {days}, файл: {'да' if file_created else 'нет'}")
        
        # Очищаем состояние
        await state.clear()
        
        try:
            await callback.answer("✅ Сертификат создан!")
        except:
            pass
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания сертификата: {e}", exc_info=True)
        
        error_message = (
            f"❌ <b>ОШИБКА СОЗДАНИЯ СЕРТИФИКАТА</b>\n\n"
            f"Произошла ошибка:\n<code>{str(e)[:200]}</code>"
        )
        
        try:
            if callback and callback.message:
                await callback.message.edit_text(error_message, parse_mode="HTML")
        except:
            try:
                if callback and callback.message:
                    await callback.message.answer(error_message, parse_mode="HTML")
            except:
                pass
        
        await state.clear()
        try:
            if callback:
                await callback.answer("❌ Ошибка")
        except:
            pass
@dp.callback_query(UserStates.admin_waiting_certificate_recipient, F.data == "certificate_general")
async def admin_certificate_general_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран общий сертификат"""
    if not callback or not callback.message:
        return
    
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        try:
            await callback.answer("⛔ Нет доступа")
        except:
            pass
        return
    
    # Сохраняем информацию о получателе как общий сертификат
    await state.update_data(
        recipient_type="general",
        recipient_id=None,
        recipient_username=None,
        recipient_name="Общий сертификат",
        recipient_info="Общий сертификат (можно подарить любому)"
    )
    
    # Спрашиваем персональное сообщение
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        certificate_name = state_data.get('certificate_name', 'Сертификат')
        days = state_data.get('certificate_days', 30)
        
        await callback.message.edit_text(
            f"✍️ <b>ДОБАВИТЬ ПЕРСОНАЛЬНОЕ СООБЩЕНИЕ?</b>\n\n"
            f"🎯 Тип: Общий сертификат\n"
            f"📅 Название: {certificate_name}\n"
            f"⏰ Срок: {days} дней\n\n"
            "📝 <b>Введите персональное сообщение для получателя:</b>\n"
            "<i>Это сообщение будет добавлено к сертификату.\n"
            "Нажмите 'Пропустить' если сообщение не нужно.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⏭️ Пропустить сообщение", callback_data="certificate_skip_message")]
                ]
            )
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        try:
            await callback.message.answer(
                "✍️ <b>ДОБАВИТЬ ПЕРСОНАЛЬНОЕ СООБЩЕНИЕ?</b>\n\n"
                "📝 <b>Введите персональное сообщение:</b>\n"
                "<i>Нажмите 'Пропустить' если не нужно</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⏭️ Пропустить сообщение", callback_data="certificate_skip_message")]
                    ]
                )
            )
        except Exception as e2:
            logger.error(f"Ошибка при отправке сообщения: {e2}")
    
    await state.set_state(UserStates.admin_waiting_certificate_message)
    
    try:
        await callback.answer("✅ Выбран общий сертификат")
    except:
        pass

@dp.callback_query(UserStates.admin_waiting_certificate_recipient, F.data == "certificate_back_to_type")
async def admin_certificate_back_to_type(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору типа сертификата"""
    if not callback or not callback.message:
        return
    
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        try:
            await callback.answer("⛔ Нет доступа")
        except:
            pass
        return
    
    # Возвращаемся к выбору типа сертификата
    try:
        await callback.message.edit_text(
            "🎁 <b>СОЗДАНИЕ СЕРТИФИКАТА</b>\n\n"
            "Выберите тип сертификата:\n\n"
            "📅 <b>Месячный (30 дней)</b> - стандартная подписка\n"
            "📆 <b>Годовой (365 дней)</b> - премиальная подписка\n\n"
            "Выберите вариант:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Месячный (30 дней)", callback_data="certificate_month")],
                    [InlineKeyboardButton(text="📆 Годовой (365 дней)", callback_data="certificate_year")],
                    [InlineKeyboardButton(text="🔙 Отмена", callback_data="certificate_cancel")]
                ]
            )
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        try:
            await callback.message.answer(
                "🎁 <b>СОЗДАНИЕ СЕРТИФИКАТА</b>\n\n"
                "Выберите тип сертификата:\n\n"
                "📅 <b>Месячный (30 дней)</b> - стандартная подписка\n"
                "📆 <b>Годовой (365 дней)</b> - премиальная подписка\n\n"
                "Выберите вариант:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📅 Месячный (30 дней)", callback_data="certificate_month")],
                        [InlineKeyboardButton(text="📆 Годовой (365 дней)", callback_data="certificate_year")],
                        [InlineKeyboardButton(text="🔙 Отмена", callback_data="certificate_cancel")]
                    ]
                )
            )
        except Exception as e2:
            logger.error(f"Ошибка при отправке сообщения: {e2}")
    
    await state.set_state(UserStates.admin_waiting_certificate_type)
    
    try:
        await callback.answer()
    except:
        pass
@dp.message(UserStates.admin_waiting_certificate_recipient)
async def admin_certificate_recipient_received(message: Message, state: FSMContext):
    """Получение информации о получателе сертификата"""
    if not message or not message.from_user:
        return
    
    if message.from_user.id != config.ADMIN_ID:
        return
    
    if not message.text:
        await message.answer(
            "❌ Введите ID пользователя или username:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎫 Создать общий сертификат", callback_data="certificate_general")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="certificate_back_to_type")]
                ]
            )
        )
        return
    
    recipient_text = message.text.strip()
    
    if not recipient_text:
        await message.answer(
            "❌ Введите ID пользователя или username:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎫 Создать общий сертификат", callback_data="certificate_general")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="certificate_back_to_type")]
                ]
            )
        )
        return
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    days = state_data.get('certificate_days', 30)
    certificate_name = state_data.get('certificate_name', 'Сертификат')
    
    # Определяем тип получателя
    recipient_id = None
    recipient_username = None
    recipient_name = ""
    
    if recipient_text.lower() == "общий":
        # Обработка текстового ввода "общий"
        recipient_type = "general"
        recipient_name = "Общий сертификат"
        recipient_info = "Общий сертификат (можно подарить любому)"
    
    elif recipient_text.isdigit():
        # ID пользователя
        try:
            recipient_id = int(recipient_text)
            # Проверяем, существует ли пользователь
            user_data = await utils.get_user(recipient_id)
            if user_data:
                recipient_name = user_data.get('first_name', 'Пользователь')
                recipient_type = "specific_user"
                recipient_info = f"👤 Для пользователя: {recipient_name} (ID: {recipient_id})"
            else:
                await message.answer(
                    f"❌ Пользователь с ID {recipient_id} не найден.\n"
                    f"Проверьте ID или создайте общий сертификат.",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🎫 Создать общий сертификат", callback_data="certificate_general")],
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="certificate_back_to_type")]
                        ]
                    )
                )
                return
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя: {e}")
            await message.answer(
                f"❌ Ошибка при поиске пользователя.\n"
                f"Проверьте ID или создайте общий сертификат.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🎫 Создать общий сертификат", callback_data="certificate_general")],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="certificate_back_to_type")]
                    ]
                )
            )
            return
    
    elif recipient_text.startswith("@"):
        # Username
        recipient_username = recipient_text[1:]  # Убираем @
        recipient_type = "by_username"
        recipient_name = f"@{recipient_username}"
        recipient_info = f"👤 Для пользователя: @{recipient_username}"
        
        # Показываем предупреждение
        await message.answer(
            f"⚠️ <b>Поиск по username</b>\n\n"
            f"Вы указали username: @{recipient_username}\n\n"
            f"📌 <b>Рекомендация:</b>\n"
            f"• Сертификат будет создан, но активировать его сможет только пользователь с таким username\n"
            f"• Лучше узнать ID пользователя через команду /find_user\n\n"
            f"✅ <b>Продолжить с username?</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Продолжить", callback_data=f"certificate_confirm_username_{recipient_username}"),
                        InlineKeyboardButton(text="🔙 Отмена", callback_data="certificate_back_to_recipient")
                    ]
                ]
            )
        )
        return
    
    else:
        # Неизвестный формат
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Введите:\n"
            "• ID пользователя (только цифры)\n"
            "• @username (например: @ivanov)\n"
            "• Или нажмите кнопку для общего сертификата",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎫 Создать общий сертификат", callback_data="certificate_general")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="certificate_back_to_type")]
                ]
            )
        )
        return
    
    # Сохраняем информацию о получателе
    await state.update_data(
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_username=recipient_username,
        recipient_name=recipient_name,
        recipient_info=recipient_info
    )
    
    # Спрашиваем персональное сообщение
    await message.answer(
        f"✍️ <b>ДОБАВИТЬ ПЕРСОНАЛЬНОЕ СООБЩЕНИЕ?</b>\n\n"
        f"{recipient_info}\n"
        f"📅 Тип: {certificate_name}\n"
        f"⏰ Срок: {days} дней\n\n"
        "📝 <b>Введите персональное сообщение для получателя:</b>\n"
        "<i>Это сообщение будет добавлено к сертификату.\n"
        "Нажмите 'Пропустить' если сообщение не нужно.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить сообщение", callback_data="certificate_skip_message")]
            ]
        )
    )
    
    await state.set_state(UserStates.admin_waiting_certificate_message)

@dp.message(UserStates.admin_waiting_certificate_message)
async def admin_certificate_message_received(message: Message, state: FSMContext):
    """Получение персонального сообщения"""
    if not message or not message.from_user:
        return
    
    if message.from_user.id != config.ADMIN_ID:
        return
    
    personal_message = message.text.strip() if message.text else ""
    
    # Сохраняем сообщение
    await state.update_data(personal_message=personal_message)
    
    # Создаем сертификат
    await create_certificate_final(message, state)

async def create_certificate_final(update, state: FSMContext):
    """Финальное создание сертификата"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        
        certificate_type = state_data.get('certificate_type', 'certificate_month')
        days = state_data.get('certificate_days', 30)
        certificate_name = state_data.get('certificate_name', 'Сертификат')
        recipient_type = state_data.get('recipient_type', 'general')
        recipient_id = state_data.get('recipient_id')
        recipient_name = state_data.get('recipient_name', 'Получатель')
        recipient_info = state_data.get('recipient_info', '')
        personal_message = state_data.get('personal_message', '')
        
        # Создаем инвайт-код для сертификата
        code_type = f"certificate_{certificate_type}"
        
        # Определяем дополнительные параметры
        extra_data = {
            "is_certificate": True,
            "certificate_name": certificate_name,
            "certificate_days": days,
            "created_by_admin": True,
            "admin_id": update.from_user.id if hasattr(update, 'from_user') else config.ADMIN_ID,
            "created_at": datetime.now().isoformat(),
            "recipient_info": recipient_info,
            "personal_message": personal_message if personal_message else None
        }
        
        # Если для конкретного пользователя, добавляем его ID
        if recipient_type == "specific_user" and recipient_id:
            extra_data["recipient_user_id"] = recipient_id
            extra_data["max_uses"] = 1
        
        # Создаем инвайт-код (будет использоваться как код активации сертификата)
        invite_code = await utils.create_invite_code(
            code_type=code_type,
            days=days,
            max_uses=1,  # Сертификат можно использовать только 1 раз
            created_by=update.from_user.id if hasattr(update, 'from_user') else config.ADMIN_ID,
            extra_data=extra_data  # Добавляем дополнительные данные
        )
        
        if not invite_code:
            raise Exception("Не удалось создать инвайт-код для сертификата")
        
        # Формируем сообщение с результатом
        admin_name = update.from_user.first_name if hasattr(update, 'from_user') and update.from_user else "Администратор"
        
        result_message = (
            f"✅ <b>СЕРТИФИКАТ СОЗДАН!</b>\n\n"
            f"🎁 <b>Тип:</b> {certificate_name}\n"
            f"⏰ <b>Срок:</b> {days} дней\n"
            f"🎫 <b>Код активации:</b>\n"
            f"<code>{invite_code}</code>\n\n"
        )
        
        # Добавляем информацию о получателе
        result_message += f"👤 <b>Для:</b> {recipient_info}\n\n"
        
        if personal_message:
            result_message += f"📝 <b>Персональное сообщение:</b>\n{personal_message}\n\n"
        
        # Инструкции по использованию
        result_message += (
            f"📋 <b>ИНСТРУКЦИЯ:</b>\n"
        )
        
        if recipient_type == "specific_user" and recipient_id:
            # Если для конкретного пользователя
            result_message += (
                f"1. Отправьте код пользователю {recipient_name}\n"
                f"2. Он должен зайти в раздел «Сертификаты 🎁»\n"
                f"3. Нажать «🎫 Активировать инвайт-код»\n"
                f"4. Ввести код и активировать подписку\n\n"
            )
        else:
            # Общий сертификат
            result_message += (
                f"1. Отправьте код любому человеку\n"
                f"2. Он должен зайти в раздел «Сертификаты 🎁»\n"
                f"3. Нажать «🎫 Активировать инвайт-код»\n"
                f"4. Ввести код и активировать подписку\n\n"
            )
        
        result_message += f"⏰ <b>Сертификат действует 90 дней</b>\n"
        result_message += f"👤 <b>Создал:</b> {admin_name}"
        
        # Если нужно создать файл сертификата (HTML)
        try:
            from certificates.spartan_generator import spartan_certificate_generator
            
            # Данные для сертификата
            certificate_data = {
                'invite_code': invite_code,
                'tariff_data': {
                    'name': certificate_name,
                    'days': days,
                    'price': 0  # Сертификат бесплатный
                },
                'buyer_data': {
                    'first_name': admin_name,
                    'username': update.from_user.username if hasattr(update, 'from_user') and update.from_user else None,
                    'user_id': update.from_user.id if hasattr(update, 'from_user') and update.from_user else 0
                },
                'recipient_info': recipient_info,
                'personal_message': personal_message,
                'created_at': datetime.now().strftime("%d.%m.%Y")
            }
            
            # Генерируем HTML контент
            html_content = spartan_certificate_generator.generate_certificate(
                invite_code=invite_code,
                tariff_data=certificate_data['tariff_data'],
                buyer_data=certificate_data['buyer_data'],
                config=config
            )
            
            # Сохраняем файл
            filepath = spartan_certificate_generator.save_certificate(f"cert_{invite_code}", html_content)
            
            # Отправляем файл администратору
            from aiogram.types import FSInputFile
            certificate_file = FSInputFile(filepath)
            
            # Отправляем отдельное сообщение с файлом
            if isinstance(update, Message):
                await update.answer_document(
                    certificate_file,
                    caption=f"📄 Файл сертификата для кода: {invite_code}"
                )
            elif isinstance(update, CallbackQuery) and update.message:
                await update.message.answer_document(
                    certificate_file,
                    caption=f"📄 Файл сертификата для кода: {invite_code}"
                )
            
            # Удаляем временный файл через 60 секунд
            await asyncio.sleep(60)
            try:
                import os
                os.remove(filepath)
                logger.info(f"🗑️ Временный файл удален: {filepath}")
            except Exception as delete_error:
                logger.error(f"Ошибка удаления файла {filepath}: {delete_error}")
                
            result_message += f"\n\n📄 <b>Файл сертификата отправлен отдельным сообщением</b>"
            
        except ImportError:
            logger.warning("Модуль генерации сертификатов не найден, отправляем только код")
        except Exception as cert_error:
            logger.error(f"Ошибка создания файла сертификата: {cert_error}")
            result_message += f"\n\n⚠️ <i>Файл сертификата не создан (ошибка: {str(cert_error)[:50]}...)</i>"
        
        # Отправляем результат
        if isinstance(update, Message):
            await update.answer(result_message, parse_mode="HTML")
        elif isinstance(update, CallbackQuery) and update.message:
            try:
                await update.message.edit_text(result_message, parse_mode="HTML")
            except:
                await update.message.answer(result_message, parse_mode="HTML")
        
        # Логируем создание
        logger.info(f"🎁 Сертификат создан: {certificate_name}, код: {invite_code}")
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания сертификата: {e}", exc_info=True)
        
        error_message = (
            f"❌ <b>ОШИБКА СОЗДАНИЯ СЕРТИФИКАТА</b>\n\n"
            f"Произошла ошибка: {str(e)[:100]}...\n\n"
            f"Попробуйте снова или обратитесь к разработчику."
        )
        
        if isinstance(update, Message):
            await update.answer(error_message, parse_mode="HTML")
        elif isinstance(update, CallbackQuery) and update.message:
            try:
                await update.message.edit_text(error_message, parse_mode="HTML")
            except:
                await update.message.answer(error_message, parse_mode="HTML")
        
        await state.clear()

@dp.message(F.text == "📋 Мои сертификаты")
async def admin_view_certificates(message: Message):
    """Просмотр созданных сертификатов"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    try:
        # Получаем все инвайт-коды
        invites = await utils.read_json(config.INVITE_CODES_FILE)
        
        if not invites or not isinstance(invites, dict):
            await message.answer("📭 Нет созданных сертификатов")
            return
        
        # Фильтруем только сертификаты
        certificates = {}
        for code, data in invites.items():
            if isinstance(data, dict) and data.get('is_certificate'):
                certificates[code] = data
        
        if not certificates:
            await message.answer("📭 Нет созданных сертификатов")
            return
        
        # Группируем по статусу
        active_certs = []
        used_certs = []
        expired_certs = []
        
        for code, cert_data in certificates.items():
            is_active = cert_data.get('is_active', True)
            used_count = cert_data.get('used_count', 0)
            max_uses = cert_data.get('max_uses', 1)
            expires_at = cert_data.get('expires_at')
            
            # Проверяем срок действия
            is_expired = False
            if expires_at:
                try:
                    expiry_date = datetime.fromisoformat(expires_at)
                    if datetime.now() > expiry_date:
                        is_expired = True
                except:
                    pass
            
            if is_expired:
                expired_certs.append((code, cert_data))
            elif used_count >= max_uses:
                used_certs.append((code, cert_data))
            elif is_active:
                active_certs.append((code, cert_data))
        
        # Формируем сообщение
        message_text = "📋 <b>СОЗДАННЫЕ СЕРТИФИКАТЫ</b>\n\n"
        
        if active_certs:
            message_text += f"🟢 <b>Активные:</b> {len(active_certs)}\n"
            for i, (code, cert_data) in enumerate(active_certs[:3], 1):
                name = cert_data.get('certificate_name', 'Сертификат')
                days = cert_data.get('certificate_days', 30)
                recipient = cert_data.get('recipient_info', 'Общий')
                message_text += f"{i}. {name} ({days}д) - {code[:8]}...\n"
            
            if len(active_certs) > 3:
                message_text += f"... и еще {len(active_certs) - 3}\n"
            message_text += "\n"
        
        if used_certs:
            message_text += f"🔴 <b>Использованные:</b> {len(used_certs)}\n"
        
        if expired_certs:
            message_text += f"⏰ <b>Просроченные:</b> {len(expired_certs)}\n"
        
        message_text += f"\n📊 <b>Всего:</b> {len(certificates)} сертификатов"
        
        # Кнопки для управления
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Создать новый", callback_data="admin_create_certificate")],
                [InlineKeyboardButton(text="📊 Детальная статистика", callback_data="admin_certificates_stats")],
                [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")]
            ]
        )
        
        await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре сертификатов: {e}")
        await message.answer(
            f"❌ Ошибка при загрузке сертификатов: {str(e)[:100]}..."
        )
 
@dp.callback_query(F.data == "admin_create_certificate")
async def admin_create_certificate_callback(callback: CallbackQuery, state: FSMContext):
    """Создание сертификата из callback"""
    user = callback.from_user
    if not user or user.id != config.ADMIN_ID:
        try:
            await callback.answer("⛔ Нет доступа")
        except:
            pass
        return
    
    # Вызываем функцию начала создания сертификата
    await admin_create_certificate_start(callback.message, state)
    
    try:
        await callback.answer()
    except:
        pass       
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


# ========== МАССОВАЯ РАССЫЛКА==========
@dp.message(Command("test_send"))
async def test_send_command(message: Message):
    """Тест отправки сообщения - ПРОСТАЯ ВЕРСИЯ"""
    if not message or not message.from_user or message.from_user.id != config.ADMIN_ID:
        return
    
    try:
        # Просто отправляем сообщение самому себе
        await bot.send_message(
            chat_id=message.from_user.id,
            text="✅ <b>ТЕСТОВОЕ СООБЩЕНИЕ</b>\n\n"
                 "Если вы видите это, значит бот может отправлять сообщения!"
        )
        await message.answer("✅ Тестовое сообщение отправлено!")
    except Exception as e:
        logger.error(f"❌ Ошибка тестовой отправки: {e}")
        await message.answer(f"❌ Ошибка: {e}")

    # НОВЫЙ СОСТОЯНИЯ
class MassNotificationState(StatesGroup):
    waiting_for_audience = State()
    waiting_for_content = State()
    confirmation = State()

# 1. Начало рассылки
# 1. Начало рассылки с добавлением фильтра "без подписки"
@dp.message(F.text == "📢 Массовая рассылка")
async def start_simple_mass_notification(message: Message, state: FSMContext):
    """Начало массовой рассылки - С ДОБАВЛЕННЫМ ФИЛЬТРОМ БЕЗ ПОДПИСКИ"""
    try:
        if not message or not message.from_user:
            return
        
        if message.from_user.id != config.ADMIN_ID:
            return
        
        # Очищаем предыдущее состояние
        await state.clear()
        
        # Создаем клавиатуру со всеми фильтрами
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👥 Всем пользователям", callback_data="mass_simple_all")],
                [InlineKeyboardButton(text="✅ Активным (30 дней)", callback_data="mass_simple_active")],
                [InlineKeyboardButton(text="❌ Неактивным (>30 дней)", callback_data="mass_simple_inactive")],
                [InlineKeyboardButton(text="💎 С подпиской", callback_data="mass_simple_subscribed")],
                [InlineKeyboardButton(text="🎁 В пробном периоде", callback_data="mass_simple_trial")],
                [InlineKeyboardButton(text="🚫 Без подписки", callback_data="mass_simple_no_sub")],  # НОВЫЙ ФИЛЬТР
                [InlineKeyboardButton(text="❌ Отмена", callback_data="mass_simple_cancel")]
            ]
        )
        
        # Получаем статистику для информации
        users = await utils.get_all_users()
        total_users = len(users)
        
        # Подсчитываем количество по фильтрам
        active_count = 0
        inactive_count = 0
        subscribed_count = 0
        trial_count = 0
        no_sub_count = 0
        
        for user_data in users.values():
            # Активные (30 дней)
            last_activity = user_data.get('last_activity')
            if last_activity:
                try:
                    last_date = datetime.fromisoformat(last_activity)
                    days_passed = (datetime.now() - last_date).days
                    if days_passed <= 30:
                        active_count += 1
                    else:
                        inactive_count += 1
                except:
                    pass
            
            # С подпиской
            if await utils.is_subscription_active(user_data):
                subscribed_count += 1
            
            # В пробном периоде
            if await utils.is_in_trial_period(user_data):
                trial_count += 1
            
            # Без подписки
            if not await utils.is_subscription_active(user_data) and not await utils.is_in_trial_period(user_data):
                no_sub_count += 1
        
        await message.answer(
            f"📢 <b>МАССОВАЯ РАССЫЛКА</b>\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ Активных: {active_count}\n"
            f"❌ Неактивных: {inactive_count}\n"
            f"💎 С подпиской: {subscribed_count}\n"
            f"🎁 В пробном: {trial_count}\n"
            f"🚫 Без подписки: {no_sub_count}\n\n"
            f"Выберите аудиторию для рассылки:",
            reply_markup=keyboard
        )
        
        await state.set_state(MassNotificationState.waiting_for_audience)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в start_simple_mass_notification: {e}")
        await message.answer("❌ Произошла ошибка")
# 2. Обработка выбора аудитории
@dp.callback_query(MassNotificationState.waiting_for_audience, F.data.startswith("mass_simple_"))
async def process_simple_audience(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора аудитории - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # 1. Проверяем все возможные None
        if callback is None:
            logger.error("❌ process_simple_audience: callback is None")
            return
        
        if not hasattr(callback, 'from_user') or callback.from_user is None:
            logger.error("❌ process_simple_audience: callback.from_user is None")
            return
        
        user = callback.from_user
        
        # 2. Проверяем права администратора
        if user.id != config.ADMIN_ID:
            try:
                await callback.answer("⛔ Нет доступа")
            except:
                pass
            return
        
        # 3. Проверяем наличие данных callback
        if not hasattr(callback, 'data') or callback.data is None:
            try:
                await callback.answer("❌ Ошибка данных")
            except:
                pass
            return
        
        # 4. Безопасно извлекаем данные
        callback_data = str(callback.data) if callback.data else ""
        
        # Проверяем что строка не пустая и содержит нужный префикс
        if not callback_data.startswith("mass_simple_"):
            try:
                await callback.answer("❌ Неверный формат данных")
            except:
                pass
            return
        
        # Безопасно извлекаем тип
        data = callback_data.replace("mass_simple_", "") if callback_data else ""
        
        if not data:
            try:
                await callback.answer("❌ Ошибка обработки данных")
            except:
                pass
            return
        
        # 5. Обработка отмены
        if data == "cancel":
            await state.clear()
            if callback and hasattr(callback, 'message') and callback.message is not None:
                try:
                    await callback.message.edit_text("❌ Рассылка отменена")
                except Exception as e:
                    logger.error(f"Ошибка редактирования сообщения: {e}")
            return
        
        # 6. Сохраняем тип аудитории
        await state.update_data(audience_type=data)
        
        # 7. Редактируем сообщение с проверкой
        if callback and hasattr(callback, 'message') and callback.message is not None:
            try:
                await callback.message.edit_text(
                    "📝 <b>Отправьте сообщение для рассылки:</b>\n\n"
                    "• Можно отправить текст\n"
                    "• Или фото с подписью\n"
                    "• Или просто фото\n\n"
                    "Сообщение будет отправлено как есть."
                )
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                # Пытаемся отправить новое сообщение
                try:
                    await bot.send_message(
                        chat_id=user.id,
                        text="📝 <b>Отправьте сообщение для рассылки:</b>\n\n"
                             "• Можно отправить текст\n"
                             "• Или фото с подписью\n"
                             "• Или просто фото\n\n"
                             "Сообщение будет отправлено как есть."
                    )
                except Exception as e2:
                    logger.error(f"Ошибка отправки сообщения: {e2}")
        
        # 8. Устанавливаем состояние
        await state.set_state(MassNotificationState.waiting_for_content)
        
        # 9. Отвечаем на callback
        try:
            await callback.answer("✅ Выберите сообщение для рассылки")
        except:
            pass
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в process_simple_audience: {e}", exc_info=True)
        
        # Пытаемся сообщить об ошибке пользователю
        try:
            if callback and hasattr(callback, 'message') and callback.message is not None:
                await callback.message.edit_text(f"❌ Произошла ошибка: {str(e)[:100]}")
        except:
            try:
                if callback and callback.from_user:
                    await bot.send_message(
                        chat_id=callback.from_user.id,
                        text="❌ Произошла ошибка при обработке запроса"
                    )
            except:
                pass

# 3. Получение контента
# 3. Получение контента - ОБНОВЛЕННАЯ ВЕРСИЯ
@dp.message(MassNotificationState.waiting_for_content)
async def process_simple_content(message: Message, state: FSMContext):
    """Получение контента для рассылки - С ДОБАВЛЕННЫМ ФИЛЬТРОМ БЕЗ ПОДПИСКИ"""
    try:
        if not message or not message.from_user or message.from_user.id != config.ADMIN_ID:
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        audience_type = data.get('audience_type', 'all')
        
        # Определяем контент
        content_type = ""
        content = ""
        photo = ""
        
        if message.text:
            content_type = 'text'
            content = message.text
        elif message.photo:
            content_type = 'photo'
            content = message.caption or ""
            if message.photo:
                photo = message.photo[-1].file_id
        else:
            await message.answer("❌ Отправьте текст или фото для рассылки")
            return
        
        # Получаем пользователей по фильтру
        users = []
        try:
            all_users = await utils.get_all_users()
            
            for user_id_str, user_data in all_users.items():
                try:
                    user_id = int(user_id_str)
                    
                    if audience_type == 'all':
                        users.append(user_id)
                        
                    elif audience_type == 'active':
                        # Активные последние 30 дней
                        last_activity = user_data.get('last_activity')
                        if last_activity:
                            last_date = datetime.fromisoformat(last_activity)
                            days_passed = (datetime.now() - last_date).days
                            if days_passed <= 30:
                                users.append(user_id)
                        else:
                            # Если нет даты активности, считаем активным
                            users.append(user_id)
                            
                    elif audience_type == 'inactive':
                        # Неактивные более 30 дней
                        last_activity = user_data.get('last_activity')
                        if last_activity:
                            last_date = datetime.fromisoformat(last_activity)
                            days_passed = (datetime.now() - last_date).days
                            if days_passed > 30:
                                users.append(user_id)
                        # Если нет даты активности, не добавляем
                            
                    elif audience_type == 'subscribed':
                        # С активной подпиской
                        if await utils.is_subscription_active(user_data):
                            users.append(user_id)
                            
                    elif audience_type == 'trial':
                        # В пробном периоде
                        if await utils.is_in_trial_period(user_data):
                            users.append(user_id)
                            
                    elif audience_type == 'no_sub':
                        # БЕЗ ПОДПИСКИ (ни подписки, ни пробного периода)
                        has_sub = await utils.is_subscription_active(user_data)
                        in_trial = await utils.is_in_trial_period(user_data)
                        if not has_sub and not in_trial:
                            users.append(user_id)
                            
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки пользователя {user_id_str}: {e}")
                    continue
                        
        except Exception as e:
            logger.error(f"❌ Ошибка фильтрации пользователей: {e}")
            await message.answer("❌ Ошибка при получении списка пользователей")
            await state.clear()
            return
        
        if not users:
            await message.answer("❌ Нет пользователей для рассылки по выбранному фильтру")
            await state.clear()
            return
        
        # Сохраняем все данные
        await state.update_data(
            content_type=content_type,
            content=content,
            photo=photo,
            users=users,
            users_count=len(users)
        )
        
        # Показываем превью
        audience_names = {
            'all': 'всем пользователям',
            'active': 'активным пользователям',
            'inactive': 'неактивным пользователям',
            'subscribed': 'с подпиской',
            'trial': 'в пробном периоде',
            'no_sub': 'без подписки'
        }
        
        preview_text = (
            f"📢 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n"
            f"👥 Аудитория: {audience_names.get(audience_type, audience_type)}\n"
            f"📊 Получателей: {len(users)}\n"
            f"📝 Тип: {'📷 Фото' if content_type == 'photo' else '📄 Текст'}\n\n"
        )
        
        if content:
            preview_text += f"<b>Содержание:</b>\n"
            preview_text += f"{content[:200]}..." if len(content) > 200 else f"{content}\n\n"
        
        preview_text += "<i>Подтвердить отправку?</i>"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, отправить", callback_data="mass_simple_confirm"),
                    InlineKeyboardButton(text="❌ Нет, отменить", callback_data="mass_simple_cancel")
                ]
            ]
        )
        
        # Отправляем превью
        try:
            if content_type == 'photo' and photo:
                # Для фото отправляем новое сообщение
                await message.answer_photo(
                    photo=photo,
                    caption=preview_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            else:
                # Для текста отправляем новое сообщение
                await message.answer(
                    preview_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки превью: {e}")
            # Если не удалось отправить с фото, пробуем без фото
            if content_type == 'photo':
                await message.answer(
                    f"{preview_text}\n\n⚠️ <i>Фото не может быть отображено в превью</i>",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            else:
                await message.answer(
                    "❌ Ошибка при создании превью",
                    reply_markup=keyboard
                )
        
        await state.set_state(MassNotificationState.confirmation)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в process_simple_content: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка обработки сообщения: {str(e)[:100]}")
        await state.clear()
# 4. Подтверждение и отправка
@dp.callback_query(MassNotificationState.confirmation, F.data.in_(["mass_simple_confirm", "mass_simple_cancel"]))
async def process_simple_confirmation(callback: CallbackQuery, state: FSMContext):
    """Подтверждение рассылки - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # 1. Проверяем callback на None
        if callback is None:
            logger.error("❌ process_simple_confirmation: callback is None")
            return
        
        # 2. Проверяем from_user на None
        if not hasattr(callback, 'from_user') or callback.from_user is None:
            logger.error("❌ process_simple_confirmation: callback.from_user is None")
            return
        
        # 3. Проверяем права администратора
        if callback.from_user.id != config.ADMIN_ID:
            try:
                await callback.answer("⛔ Нет доступа")
            except:
                pass
            return
        
        # 4. Проверяем callback.data на None
        if not hasattr(callback, 'data') or callback.data is None:
            try:
                await callback.answer("❌ Ошибка данных")
            except:
                pass
            await state.clear()
            return
        
        # 5. Обработка отмены
        if callback.data == "mass_simple_cancel":
            await state.clear()
            
            # Безопасно редактируем сообщение
            if hasattr(callback, 'message') and callback.message is not None:
                try:
                    await callback.message.edit_text("❌ Рассылка отменена")
                except Exception as e:
                    logger.error(f"Ошибка редактирования сообщения: {e}")
                    try:
                        await callback.message.delete()
                    except:
                        pass
                    try:
                        await bot.send_message(
                            chat_id=callback.from_user.id,
                            text="❌ Рассылка отменена"
                        )
                    except:
                        pass
            
            # Безопасно отвечаем на callback
            try:
                await callback.answer()
            except:
                pass
            return
        
        # 6. Проверка на подтверждение
        if callback.data != "mass_simple_confirm":
            try:
                await callback.answer("❌ Неизвестная команда")
            except:
                pass
            await state.clear()
            return
        
        # 7. Получаем данные из состояния
        data = await state.get_data()
        content_type = data.get('content_type')
        content = data.get('content', '')
        photo = data.get('photo', '')
        users = data.get('users', [])
        
        # 8. Проверяем наличие пользователей
        if not users:
            if hasattr(callback, 'message') and callback.message is not None:
                try:
                    await callback.message.edit_text("❌ Нет пользователей для рассылки")
                except:
                    pass
            await state.clear()
            try:
                await callback.answer()
            except:
                pass
            return
        
        # 9. Удаляем исходное сообщение с фото (если оно есть)
        original_message = None
        if hasattr(callback, 'message') and callback.message is not None:
            original_message = callback.message
            try:
                await original_message.delete()
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения: {e}")
                # Не прерываем выполнение, если не удалось удалить
        
        # 10. Отправляем новое сообщение о начале рассылки
        status_message = None
        try:
            status_message = await bot.send_message(
                chat_id=callback.from_user.id,
                text=(
                    f"🔄 <b>Начинаю отправку...</b>\n\n"
                    f"Получателей: {len(users)}\n"
                    f"Отправлено: 0/{len(users)}"
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки статусного сообщения: {e}")
            # Если не удалось отправить, пытаемся использовать оригинальное сообщение
            if original_message is not None:
                try:
                    status_message = await original_message.answer(
                        f"🔄 <b>Начинаю отправку...</b>\n\n"
                        f"Получателей: {len(users)}\n"
                        f"Отправлено: 0/{len(users)}"
                    )
                except:
                    pass
        
        sent_count = 0
        failed_count = 0
        
        # 11. Отправляем сообщения пользователям
        for i, user_id in enumerate(users, 1):
            try:
                if content_type == 'photo' and photo:
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=photo,
                        caption=content if content else None,
                        parse_mode='HTML'
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id,
                        text=content,
                        parse_mode='HTML'
                    )
                
                sent_count += 1
                
                # 12. Обновляем прогресс каждые 10 сообщений
                if (i % 10 == 0 or i == len(users)) and status_message is not None:
                    try:
                        await status_message.edit_text(
                            f"🔄 <b>Отправка...</b>\n\n"
                            f"Получателей: {len(users)}\n"
                            f"Отправлено: {i}/{len(users)} ({int((i/len(users))*100)}%)\n"
                            f"✅ Успешно: {sent_count}\n"
                            f"❌ Неудачно: {failed_count}"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка обновления прогресса: {e}")
                        # Если не удалось отредактировать, отправляем новое сообщение
                        try:
                            status_message = await bot.send_message(
                                chat_id=callback.from_user.id,
                                text=(
                                    f"🔄 <b>Отправка...</b>\n\n"
                                    f"Получателей: {len(users)}\n"
                                    f"Отправлено: {i}/{len(users)} ({int((i/len(users))*100)}%)\n"
                                    f"✅ Успешно: {sent_count}\n"
                                    f"❌ Неудачно: {failed_count}"
                                ),
                                parse_mode='HTML'
                            )
                        except:
                            pass
                
                # 13. Пауза чтобы не перегружать API
                if i % 20 == 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
        
        # 14. Итоговое сообщение
        result_text = (
            f"✅ <b>РАССЫЛКА ЗАВЕРШЕНА</b>\n\n"
            f"📊 <b>Итоги:</b>\n"
            f"• Всего получателей: {len(users)}\n"
            f"• Успешно отправлено: {sent_count}\n"
            f"• Не удалось отправить: {failed_count}\n\n"
        )
        
        if failed_count > 0:
            result_text += "⚠️ <i>Некоторым пользователям не удалось отправить сообщение.</i>"
        
        # 15. Отправляем итоговое сообщение
        if status_message is not None:
            try:
                await status_message.edit_text(result_text)
            except Exception as e:
                logger.error(f"Ошибка редактирования итогового сообщения: {e}")
                try:
                    await bot.send_message(
                        chat_id=callback.from_user.id,
                        text=result_text,
                        parse_mode='HTML'
                    )
                except:
                    pass
        else:
            try:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text=result_text,
                    parse_mode='HTML'
                )
            except:
                pass
        
        # 16. Очищаем состояние
        await state.clear()
        
        # 17. Безопасно отвечаем на callback
        try:
            await callback.answer("✅ Рассылка завершена")
        except Exception as e:
            logger.error(f"Ошибка ответа на callback: {e}")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в process_simple_confirmation: {e}", exc_info=True)
        
        # Пытаемся сообщить об ошибке
        try:
            if callback and hasattr(callback, 'from_user') and callback.from_user is not None:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text=f"❌ Ошибка при отправке: {str(e)[:100]}"
                )
        except:
            pass
        
        # Очищаем состояние
        try:
            await state.clear()
        except:
            pass
        
        # Безопасно отвечаем на callback
        try:
            if callback is not None:
                await callback.answer("❌ Ошибка")
        except:
            pass

# ========== СИСТЕМА УВЕДОМЛЕНИЙ ==========

class SubscriptionNotifications:
    """Класс для умных уведомлений о подписке"""
    
    @staticmethod
    async def check_all_users_for_subscription_notifications():
        """Проверяет ВСЕХ пользователей и отправляет нужные уведомления"""
        logger.info("🔔 Начинаем комплексную проверку подписок...")
        
        users = await utils.get_all_users()
        total_notifications = 0
        
        for user_id_str, user_data in users.items():
            try:
                user_id = int(user_id_str)
                
                # 1. Проверяем и отправляем уведомления этому пользователю
                sent = await SubscriptionNotifications.check_user_for_notifications(
                    user_id, user_data
                )
                
                if sent:
                    total_notifications += 1
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки пользователя {user_id_str}: {e}")
        
        logger.info(f"📊 Отправлено уведомлений: {total_notifications}")
        return total_notifications
    
    @staticmethod
    async def check_user_for_notifications(user_id: int, user_data: dict) -> bool:
        """Проверяет одного пользователя и отправляет нужные уведомления"""
        try:
            # Получаем гендерные окончания
            gender = await utils.get_gender_ending(user_data)
            
            # 🔥 1. Пользователи, прошедшие пробный период (3 задания)
            if await SubscriptionNotifications.should_notify_trial_completed(user_data):
                await SubscriptionNotifications.send_trial_completed_notification(user_id, user_data, gender)
                # Помечаем как уведомленного
                user_data['trial_completed_notified'] = True
                user_data['last_subscription_notification'] = datetime.now().isoformat()
                await utils.save_user(user_id, user_data)
                return True
            
            # 🔥 2. Пользователи с закончившейся платной подпиской
            if await SubscriptionNotifications.should_notify_subscription_ended(user_data):
                days_since_end = await SubscriptionNotifications.get_days_since_subscription_end(user_data)
                
                if days_since_end == 1:  # Первый день после окончания
                    await SubscriptionNotifications.send_subscription_ended_notification(user_id, user_data, gender)
                    user_data['subs_ended_notified'] = True
                    
                elif days_since_end == 3:  # Через 3 дня
                    await SubscriptionNotifications.send_subscription_reminder_3_days(user_id, user_data, gender)
                    user_data['subs_reminder_3d_sent'] = True
                    
                elif days_since_end == 7:  # Через неделю
                    await SubscriptionNotifications.send_subscription_reminder_7_days(user_id, user_data, gender)
                    user_data['subs_reminder_7d_sent'] = True
                    
                elif days_since_end >= 14 and days_since_end % 7 == 0:  # Каждую неделю после 2-х недель
                    await SubscriptionNotifications.send_weekly_reminder(user_id, user_data, gender, days_since_end)
                
                user_data['last_subscription_notification'] = datetime.now().isoformat()
                await utils.save_user(user_id, user_data)
                return True
            
            # 🔥 3. Пользователи, которые давно не получали уведомлений
            if await SubscriptionNotifications.should_send_periodic_reminder(user_data):
                await SubscriptionNotifications.send_periodic_reminder(user_id, user_data, gender)
                user_data['last_subscription_notification'] = datetime.now().isoformat()
                user_data['periodic_reminders_sent'] = user_data.get('periodic_reminders_sent', 0) + 1
                await utils.save_user(user_id, user_data)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки уведомлений для {user_id}: {e}")
            return False
    
    @staticmethod
    async def should_notify_trial_completed(user_data: dict) -> bool:
        """Нужно ли уведомить о завершении пробного периода"""
        try:
            # Пользователь в пробном периоде?
            in_trial = await utils.is_in_trial_period(user_data)
            if not in_trial:
                return False
            
            # Выполнил 3 задания?
            trial_tasks = user_data.get('completed_tasks_in_trial', 0)
            if trial_tasks < 3:
                return False
            
            # Еще не уведомляли?
            if user_data.get('trial_completed_notified'):
                return False
            
            # Проверяем, когда последний раз уведомляли
            last_notification = user_data.get('last_subscription_notification')
            if last_notification:
                last_date = datetime.fromisoformat(last_notification)
                days_since_last = (datetime.now() - last_date).days
                # Не уведомляем чаще чем раз в 3 дня
                if days_since_last < 3:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки пробного периода: {e}")
            return False
    
    @staticmethod
    async def should_notify_subscription_ended(user_data: dict) -> bool:
        """Нужно ли уведомить об окончании платной подписки"""
        try:
            # Проверяем активную подписку
            if await utils.is_subscription_active(user_data):
                return False
            
            # Проверяем пробный период
            if await utils.is_in_trial_period(user_data):
                return False
            
            # Проверяем дату окончания подписки
            subscription_end = user_data.get('subscription_end')
            if not subscription_end:
                return False
            
            end_date = datetime.fromisoformat(subscription_end)
            days_since_end = (datetime.now() - end_date).days
            
            # Не уведомляем если подписка закончилась меньше дня назад
            if days_since_end < 1:
                return False
            
            # Проверяем когда последний раз уведомляли
            last_notification = user_data.get('last_subscription_notification')
            if last_notification:
                last_date = datetime.fromisoformat(last_notification)
                days_since_last_notification = (datetime.now() - last_date).days
                
                # Для разных этапов разные интервалы
                if days_since_end == 1:  # Первый день - всегда уведомляем
                    return not user_data.get('subs_ended_notified', False)
                elif days_since_end == 3:  # 3 дня
                    return not user_data.get('subs_reminder_3d_sent', False) and days_since_last_notification >= 2
                elif days_since_end == 7:  # 7 дней
                    return not user_data.get('subs_reminder_7d_sent', False) and days_since_last_notification >= 3
                elif days_since_end >= 14 and days_since_end % 7 == 0:  # Каждую неделю
                    return days_since_last_notification >= 7
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки окончания подписки: {e}")
            return False
    
    @staticmethod
    async def get_days_since_subscription_end(user_data: dict) -> int:
        """Возвращает сколько дней прошло с окончания подписки"""
        try:
            subscription_end = user_data.get('subscription_end')
            if not subscription_end:
                return 0
            
            end_date = datetime.fromisoformat(subscription_end)
            return (datetime.now() - end_date).days
            
        except:
            return 0
    
    @staticmethod
    async def should_send_periodic_reminder(user_data: dict) -> bool:
        """Нужно ли отправить периодическое напоминание"""
        try:
            # Пропускаем пользователей с активной подпиской
            if await utils.is_subscription_active(user_data):
                return False
            
            # Проверяем пробный период (только если не завершили 3 задания)
            if await utils.is_in_trial_period(user_data):
                trial_tasks = user_data.get('completed_tasks_in_trial', 0)
                if trial_tasks < 3:  # Еще не завершили пробный период
                    return False
            
            # Проверяем когда последний раз уведомляли
            last_notification = user_data.get('last_subscription_notification')
            if not last_notification:
                # Никогда не уведомляли - отправляем через 5 дней после регистрации
                created_at = datetime.fromisoformat(user_data.get('created_at', datetime.now().isoformat()))
                days_since_registration = (datetime.now() - created_at).days
                return days_since_registration >= 5
            else:
                last_date = datetime.fromisoformat(last_notification)
                days_since_last = (datetime.now() - last_date).days
                
                # Отправляем напоминание раз в 10 дней
                return days_since_last >= 10
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки периодических напоминаний: {e}")
            return False

    @staticmethod
    async def send_trial_completed_notification(user_id: int, user_data: dict, gender: dict):
        """Уведомление о завершении пробного периода"""
        try:
            message_text = (
                f"🎯 <b>Пробный период завершен!</b>\n\n"
                f"Ты {gender['verb_finished']} 3 пробных задания и получил{gender['ending_a']} представление о системе.\n\n"
                f"💪 <b>Что тебя ждет в полной версии:</b>\n"
                f"• Ежедневные задания для развития силы воли\n"
                f"• Система рангов и достижений\n"
                f"• Поддержка комьюнити\n"
                f"• 297 дней роста впереди!\n"
                f"• Реферальная программа с заработком\n\n"
                f"🔥 <b>Продолжи путь к сильной версии себя!</b>\n\n"
                f"💰 <b>Выбери подходящий тариф:</b>"
            )
            
            from keyboards import get_payment_keyboard
            keyboard = get_payment_keyboard()
            
            await safe_send_message(user_id, message_text, reply_markup=keyboard)
            logger.info(f"✅ Уведомление о конце пробного периода отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о пробном периоде {user_id}: {e}")
    
    @staticmethod
    async def send_subscription_ended_notification(user_id: int, user_data: dict, gender: dict):
        """Уведомление об окончании платной подписки (день 1)"""
        try:
            completed_tasks = user_data.get('completed_tasks', 0)
            current_rank = user_data.get('rank', 'путник')
            
            message_text = (
                f"📅 <b>Ваша подписка закончилась</b>\n\n"
                f"Доступ к ежедневным заданиям приостановлен.\n\n"
                f"🏆 <b>Твои достижения сохранены:</b>\n"
                f"• Выполнено заданий: {completed_tasks}\n"
                f"• Текущий ранг: {current_rank}\n"
                f"• Прогресс: {(completed_tasks/300)*100:.1f}%\n\n"
                f"💪 <b>Не останавливайся{gender['ending']} на достигнутом!</b>\n"
                f"Продолжай{gender['ending']} развивать дисциплину с новой подпиской!\n\n"
                f"🔥 <b>Активируй{gender['ending_te']} подписку и продолжай{gender['ending']} путь!</b>"
            )
            
            from keyboards import get_payment_keyboard
            keyboard = get_payment_keyboard()
            
            await safe_send_message(user_id, message_text, reply_markup=keyboard)
            logger.info(f"✅ Уведомление об окончании подписки отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления об окончании подписки {user_id}: {e}")
    
    @staticmethod
    async def send_subscription_reminder_3_days(user_id: int, user_data: dict, gender: dict):
        """Напоминание через 3 дня после окончания подписки"""
        try:
            message_text = (
                f"⏰ <b>Скучаем по тебе в челлендже!</b>\n\n"
                f"Прошло 3 дня с момента окончания подписки.\n\n"
                f"🎯 <b>Помни, что тебя ждет:</b>\n"
                f"• Ежедневные победы над собой\n"
                f"• Новые ранги и привилегии\n"
                f"• Рост силы воли и дисциплины\n"
                f"• Комьюнити единомышленников\n\n"
                f"💪 <b>Вернись и продолжай{gender['ending']} путь к сильной версии себя!</b>\n"
                f"Твое место в челлендже все еще свободно."
            )
            
            from keyboards import get_payment_keyboard
            keyboard = get_payment_keyboard()
            
            await safe_send_message(user_id, message_text, reply_markup=keyboard)
            logger.info(f"✅ Напоминание о подписке (3 дня) отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминания (3 дня) {user_id}: {e}")
    
    @staticmethod
    async def send_subscription_reminder_7_days(user_id: int, user_data: dict, gender: dict):
        """Напоминание через 7 дней после окончания подписки"""
        try:
            completed_tasks = user_data.get('completed_tasks', 0)
            
            message_text = (
                f"📅 <b>Неделя без челленджа</b>\n\n"
                f"Уже 7 дней прошло с момента окончания подписки.\n\n"
                f"🎯 <b>Твой прогресс заморожен на {completed_tasks} задании:</b>\n"
                f"• Каждый день без подписки - потерянный день роста\n"
                f"• Дисциплина требует постоянства\n"
                f"• Сила воли слабеет без тренировки\n\n"
                f"🔥 <b>Вернись в строй пока не забыл{gender['ending']} навыки!</b>\n"
                f"Активируй{gender['ending_te']} подписку и продолжай{gender['ending']} с того места, где остановил{gender['ending']}ся."
            )
            
            from keyboards import get_payment_keyboard
            keyboard = get_payment_keyboard()
            
            await safe_send_message(user_id, message_text, reply_markup=keyboard)
            logger.info(f"✅ Напоминание о подписке (7 дней) отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминания (7 дней) {user_id}: {e}")
    
    @staticmethod
    async def send_weekly_reminder(user_id: int, user_data: dict, gender: dict, days_since_end: int):
        """Еженедельное напоминание после 2-х недель"""
        try:
            weeks = days_since_end // 7
            
            message_text = (
                f"📆 <b>Прошло {weeks} недель</b>\n\n"
                f"Уже {days_since_end} дней ты не получаешь задания.\n\n"
                f"💡 <b>Знаешь ли ты, что:</b>\n"
                f"• Привычка формируется 21 день\n"
                f"• Дисциплина - это навык\n"
                f"• Каждый день важен для прогресса\n\n"
                f"🎯 <b>Не откладывай{gender['ending']} свою трансформацию!</b>\n"
                f"Вернись в челлендж сегодня - завтра может быть поздно."
            )
            
            from keyboards import get_payment_keyboard
            keyboard = get_payment_keyboard()
            
            await safe_send_message(user_id, message_text, reply_markup=keyboard)
            logger.info(f"✅ Еженедельное напоминание ({weeks} недель) отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки еженедельного напоминания {user_id}: {e}")
    
    @staticmethod
    async def send_periodic_reminder(user_id: int, user_data: dict, gender: dict):
        """Периодическое напоминание (раз в 10 дней)"""
        try:
            reminders_sent = user_data.get('periodic_reminders_sent', 0) + 1
            
            if reminders_sent == 1:
                message_text = (
                    f"⏰ <b>Привет! Скучаем по тебе в челлендже!</b>\n\n"
                    f"Заметили, что ты давно не получал{gender['ending']} задания.\n\n"
                    f"💪 <b>Напомним, зачем нужен челлендж:</b>\n"
                    f"• Развитие силы воли\n"
                    f"• Ежедневный рост\n"
                    f"• Дисциплина и порядок\n"
                    f"• Сообщество единомышленников\n\n"
                    f"🔥 <b>Вернись к своей трансформации!</b>"
                )
            elif reminders_sent == 2:
                message_text = (
                    f"🎯 <b>Твоя сильная версия ждет тебя!</b>\n\n"
                    f"Каждый день отсрочки - отложенная победа.\n\n"
                    f"💡 <b>Почему сейчас лучшее время вернуться:</b>\n"
                    f"• Прогресс сохраняется\n"
                    f"• Сообщество поддерживает\n"
                    f"• Задания ждут выполнения\n"
                    f"• Ты уже начал{gender['ending']} путь\n\n"
                    f"🚀 <b>Продолжи{gender['ending']} с того места, где остановил{gender['ending']}ся!</b>"
                )
            else:
                message_text = (
                    f"⚡ <b>Последний шанс вернуться!</b>\n\n"
                    f"Система скоро очистит неактивные аккаунты.\n\n"
                    f"⚠️ <b>Твой прогресс может быть утерян:</b>\n"
                    f"• {user_data.get('completed_tasks', 0)} выполненных заданий\n"
                    f"• Ранг {user_data.get('rank', 'путник')}\n"
                    f"• Достижения и привилегии\n\n"
                    f"🔥 <b>Активируй{gender['ending_te']} подписку сейчас чтобы сохранить прогресс!</b>"
                )
            
            from keyboards import get_payment_keyboard
            keyboard = get_payment_keyboard()
            
            await safe_send_message(user_id, message_text, reply_markup=keyboard)
            logger.info(f"✅ Периодическое напоминание #{reminders_sent} отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки периодического напоминания {user_id}: {e}")

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

class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    admin_viewing_users = State()
    admin_viewing_user_details = State()
    admin_waiting_user_message = State()
    admin_waiting_add_days = State()

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
async def admin_users(message: Message, state: FSMContext):
    """Управление пользователями - ПОЛНЫЙ СПИСОК С ПАГИНАЦИЕЙ"""
    user = message.from_user
    if not user or user.id != config.ADMIN_ID:
        return
    
    try:
        # Очищаем состояние
        await state.clear()
        
        # Получаем всех пользователей
        users = await utils.get_all_users()
        
        if not users:
            await message.answer(
                "👥 <b>Пользователи</b>\n\n"
                "В базе нет пользователей.",
                reply_markup=keyboards.get_admin_users_keyboard()
            )
            return
        
        # Преобразуем в список и сортируем по дате регистрации (новые первые)
        users_list = []
        for user_id_str, user_data in users.items():
            try:
                user_id = int(user_id_str)
                users_list.append((user_id, user_data))
            except:
                continue
        
        # Сортируем по дате создания
        users_list.sort(
            key=lambda x: x[1].get('created_at', ''), 
            reverse=True
        )
        
        # Сохраняем в состояние
        await state.update_data(
            admin_users_list=users_list,
            admin_users_page=0,
            admin_users_total=len(users_list)
        )
        
        # Показываем первую страницу
        await show_users_page(message, state, page=0)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в admin_users: {e}")
        await message.answer(
            f"❌ Ошибка загрузки пользователей: {str(e)[:100]}",
            reply_markup=keyboards.get_admin_users_keyboard()
        )

@dp.message(AdminStates.admin_viewing_users)
async def admin_users_search_process(message: Message, state: FSMContext):
    """Обработка поискового запроса - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # 1. Проверяем message на None
        if message is None:
            logger.error("❌ admin_users_search_process: message is None")
            return
        
        # 2. Проверяем from_user на None
        if not hasattr(message, 'from_user') or message.from_user is None:
            logger.error("❌ admin_users_search_process: message.from_user is None")
            return
        
        # 3. Проверяем права администратора
        if message.from_user.id != config.ADMIN_ID:
            return
        
        # 4. Проверяем текст на None
        if not hasattr(message, 'text') or message.text is None:
            await message.answer("❌ Введите текст для поиска")
            return
        
        search_query = message.text.strip()
        
        if not search_query:
            await message.answer("❌ Введите текст для поиска")
            return
        
        await message.answer(f"🔍 <b>Поиск:</b> '{search_query}'...")
        
        # 5. Получаем всех пользователей
        users = await utils.get_all_users()
        results = []
        
        for user_id_str, user_data in users.items():
            try:
                user_id = int(user_id_str)
                
                # Поиск по ID
                if search_query.isdigit() and int(search_query) == user_id:
                    results.append((user_id, user_data))
                    continue
                
                # Поиск по username (без @)
                username = user_data.get('username', '').lower()
                if search_query.lower().lstrip('@') in username:
                    results.append((user_id, user_data))
                    continue
                
                # Поиск по имени
                first_name = user_data.get('first_name', '').lower()
                if search_query.lower() in first_name:
                    results.append((user_id, user_data))
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки пользователя {user_id_str}: {e}")
                continue
        
        # 6. Клавиатура для возврата
        back_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users_back")]
            ]
        )
        
        if not results:
            await message.answer(
                f"❌ Пользователи по запросу '{search_query}' не найдены",
                reply_markup=back_keyboard
            )
            return
        
        # 7. Сохраняем результаты в состояние
        await state.update_data(
            admin_users_list=results,
            admin_users_page=0
        )
        
        # 8. Показываем первую страницу результатов
        await show_users_page(message, state, page=0)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в admin_users_search_process: {e}", exc_info=True)
        await message.answer("❌ Ошибка при поиске")
        
@dp.callback_query(F.data == "admin_users_search")
async def admin_users_search_handler(callback: CallbackQuery, state: FSMContext):
    """Поиск пользователей - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # 1. Проверяем callback на None
        if callback is None:
            logger.error("❌ admin_users_search_handler: callback is None")
            return
        
        # 2. Проверяем from_user на None
        if not hasattr(callback, 'from_user') or callback.from_user is None:
            logger.error("❌ admin_users_search_handler: callback.from_user is None")
            return
        
        # 3. Проверяем права администратора
        if callback.from_user.id != config.ADMIN_ID:
            try:
                await callback.answer("⛔ Нет доступа")
            except:
                pass
            return
        
        # 4. Проверяем message на None
        if not hasattr(callback, 'message') or callback.message is None:
            try:
                await callback.answer("❌ Ошибка: сообщение не найдено")
            except:
                pass
            return
        
        # 5. Создаем клавиатуру для поиска
        search_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users_back")]
            ]
        )
        
        # 6. Безопасно редактируем сообщение
        try:
            await callback.message.edit_text(
                "🔍 <b>ПОИСК ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
                "Введите для поиска:\n"
                "• ID пользователя (только цифры)\n"
                "• @username\n"
                "• Имя или часть имени\n\n"
                "Примеры:\n"
                "<code>123456789</code>\n"
                "<code>@username</code>\n"
                "<code>Иван</code>\n\n"
                "Или нажмите кнопку ниже для просмотра всех пользователей:",
                reply_markup=search_keyboard
            )
        except Exception as e:
            logger.error(f"❌ Ошибка редактирования сообщения: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение
            try:
                await callback.message.answer(
                    "🔍 <b>ПОИСК ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
                    "Введите для поиска:\n"
                    "• ID пользователя (только цифры)\n"
                    "• @username\n"
                    "• Имя или часть имени\n\n"
                    "Примеры:\n"
                    "<code>123456789</code>\n"
                    "<code>@username</code>\n"
                    "<code>Иван</code>\n\n"
                    "Или нажмите кнопку ниже для просмотра всех пользователей:",
                    reply_markup=search_keyboard
                )
            except:
                pass
        
        # 7. Устанавливаем состояние для поиска
        await state.set_state(AdminStates.admin_viewing_users)
        
        # 8. Безопасно отвечаем на callback
        try:
            await callback.answer("🔍 Введите запрос для поиска")
        except:
            pass
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в admin_users_search_handler: {e}", exc_info=True)
        try:
            await callback.answer("❌ Ошибка")
        except:
            pass

async def show_users_page(message_or_callback, state: FSMContext, page: int):
    """Показывает страницу со списком пользователей - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        users_list = data.get('admin_users_list', [])
        total_users = len(users_list)
        
        if not users_list:
            text = "👥 <b>Пользователи</b>\n\nВ базе нет пользователей."
            
            # Проверяем тип и отправляем сообщение
            if isinstance(message_or_callback, CallbackQuery):
                if message_or_callback is not None and hasattr(message_or_callback, 'message') and message_or_callback.message is not None:
                    try:
                        await message_or_callback.message.edit_text(
                            text,
                            reply_markup=keyboards.get_admin_users_keyboard()
                        )
                    except Exception as e:
                        logger.error(f"Ошибка редактирования: {e}")
                        await message_or_callback.message.answer(
                            text,
                            reply_markup=keyboards.get_admin_users_keyboard()
                        )
                try:
                    await message_or_callback.answer()
                except:
                    pass
            else:
                if message_or_callback is not None:
                    await message_or_callback.answer(
                        text,
                        reply_markup=keyboards.get_admin_users_keyboard()
                    )
            return
        
        # Настройки пагинации
        USERS_PER_PAGE = 15
        total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        
        # Корректируем номер страницы
        page = max(0, min(page, total_pages - 1))
        start_idx = page * USERS_PER_PAGE
        end_idx = min(start_idx + USERS_PER_PAGE, total_users)
        
        # Сохраняем текущую страницу
        await state.update_data(
            admin_users_page=page,
            admin_users_total_pages=total_pages
        )
        
        # Формируем текст
        text = (
            f"👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ</b>\n"
            f"📊 Всего: {total_users} | Страница {page + 1}/{total_pages}\n\n"
        )
        
        # Добавляем пользователей на текущей странице
        for i, (user_id, user_data) in enumerate(users_list[start_idx:end_idx], start_idx + 1):
            # Основная информация
            first_name = user_data.get('first_name', 'Без имени')
            username = user_data.get('username', '')
            archetype = user_data.get('archetype', 'spartan')
            archetype_icon = '🛡️' if archetype == 'spartan' else '⚔️'
            
            # Статус подписки
            if await utils.is_subscription_active(user_data):
                status = '💎'  # Платная подписка
            elif await utils.is_in_trial_period(user_data):
                status = '🎁'  # Пробный период
            else:
                status = '❌'  # Нет подписки
            
            # День и выполненные задания
            current_day = user_data.get('current_day', 0)
            completed_tasks = user_data.get('completed_tasks', 0)
            rank = user_data.get('rank', 'putnik')
            
            # Форматируем username
            username_display = f"@{username}" if username else "нет username"
            
            # Делаем ID кликабельным для просмотра деталей
            text += (
                f"{i}. {status} {archetype_icon} <b>{first_name}</b>\n"
                f"   🆔 <code>{user_id}</code> | 📱 {username_display}\n"
                f"   📅 День {current_day} | ✅ {completed_tasks} зад. | 🏆 {rank}\n"
            )
            
            # Добавляем дату регистрации
            created_at = user_data.get('created_at', '')
            if created_at:
                created_short = created_at[:10] if len(created_at) > 10 else created_at
                text += f"   📆 Регистрация: {created_short}\n"
            
            text += "\n"
        
        # Создаем клавиатуру с пагинацией
        keyboard_buttons = []
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="◀️ Пред.", 
                callback_data=f"admin_users_page_{page - 1}"
            ))
        
        nav_buttons.append(InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}", 
            callback_data="admin_users_current_page"
        ))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(
                text="След. ▶️", 
                callback_data=f"admin_users_page_{page + 1}"
            ))
        
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
        
        # Кнопки поиска и экспорта
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔍 Поиск", callback_data="admin_users_search"),
            InlineKeyboardButton(text="📥 Экспорт", callback_data="admin_users_export")
        ])
        
        # Кнопка назад
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Отправляем или редактируем сообщение
        if isinstance(message_or_callback, CallbackQuery):
            if message_or_callback is not None and hasattr(message_or_callback, 'message') and message_or_callback.message is not None:
                try:
                    await message_or_callback.message.edit_text(text, reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Ошибка редактирования: {e}")
                    try:
                        await message_or_callback.message.answer(text, reply_markup=keyboard)
                    except:
                        pass
            try:
                await message_or_callback.answer()
            except:
                pass
        else:
            if message_or_callback is not None:
                await message_or_callback.answer(text, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в show_users_page: {e}", exc_info=True)
        if isinstance(message_or_callback, CallbackQuery):
            try:
                await message_or_callback.answer("❌ Ошибка загрузки")
            except:
                pass

@dp.callback_query(F.data.startswith("admin_users_page_"))
async def admin_users_page_handler(callback: CallbackQuery, state: FSMContext):
    """Переключение страниц списка пользователей - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # 1. Проверяем callback на None
        if callback is None:
            logger.error("❌ admin_users_page_handler: callback is None")
            return
        
        # 2. Проверяем from_user на None
        if not hasattr(callback, 'from_user') or callback.from_user is None:
            logger.error("❌ admin_users_page_handler: callback.from_user is None")
            return
        
        # 3. Проверяем права администратора
        if callback.from_user.id != config.ADMIN_ID:
            try:
                await callback.answer("⛔ Нет доступа")
            except:
                pass
            return
        
        # 4. Проверяем data на None
        if not hasattr(callback, 'data') or callback.data is None:
            try:
                await callback.answer("❌ Ошибка данных")
            except:
                pass
            return
        
        # 5. Безопасно извлекаем номер страницы
        try:
            callback_data = str(callback.data)
            page = int(callback_data.replace("admin_users_page_", ""))
        except (ValueError, AttributeError) as e:
            logger.error(f"❌ Ошибка преобразования страницы: {e}")
            try:
                await callback.answer("❌ Неверный номер страницы")
            except:
                pass
            return
        
        # 6. Получаем данные из состояния
        data = await state.get_data()
        users_list = data.get('admin_users_list', [])
        
        # 7. Если список пуст, загружаем всех пользователей
        if not users_list:
            users = await utils.get_all_users()
            users_list = []
            for user_id_str, user_data in users.items():
                try:
                    users_list.append((int(user_id_str), user_data))
                except:
                    continue
            
            # Сортируем по дате создания
            users_list.sort(
                key=lambda x: x[1].get('created_at', ''), 
                reverse=True
            )
            
            # Сохраняем в состояние
            await state.update_data(
                admin_users_list=users_list,
                admin_users_page=page
            )
        
        # 8. Показываем страницу
        await show_users_page(callback, state, page)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в admin_users_page_handler: {e}", exc_info=True)
        try:
            await callback.answer("❌ Ошибка")
        except:
            pass

@dp.callback_query(F.data == "admin_users_export")
async def admin_users_export_handler(callback: CallbackQuery, state: FSMContext):
    """Экспорт списка пользователей в CSV"""
    try:
        if callback is None:
            return
        
        if not hasattr(callback, 'from_user') or callback.from_user is None:
            return
        
        if callback.from_user.id != config.ADMIN_ID:
            try:
                await callback.answer("⛔ Нет доступа")
            except:
                pass
            return
        
        if not hasattr(callback, 'message') or callback.message is None:
            try:
                await callback.answer("❌ Ошибка сообщения")
            except:
                pass
            return
        
        data = await state.get_data()
        users_list = data.get('admin_users_list', [])
        
        if not users_list:
            users = await utils.get_all_users()
            users_list = []
            for user_id_str, user_data in users.items():
                try:
                    users_list.append((int(user_id_str), user_data))
                except:
                    continue
        
        if not users_list:
            await callback.answer("❌ Нет пользователей для экспорта")
            return
        
        # Создаем CSV файл
        import csv
        import io
        from datetime import datetime
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовки
        writer.writerow([
            'ID', 'Имя', 'Username', 'Архетип', 'Часовой пояс',
            'День', 'Заданий', 'Ранг', 'Подписка', 'Пробный',
            'Рефералов', 'Заработано', 'Дата регистрации', 'Последняя активность'
        ])
        
        # Данные
        for user_id, user_data in users_list:
            archetype = user_data.get('archetype', 'spartan')
            has_sub = await utils.is_subscription_active(user_data)
            in_trial = await utils.is_in_trial_period(user_data)
            
            writer.writerow([
                user_id,
                user_data.get('first_name', ''),
                user_data.get('username', ''),
                'Спартанец' if archetype == 'spartan' else 'Амазонка',
                user_data.get('timezone', ''),
                user_data.get('current_day', 0),
                user_data.get('completed_tasks', 0),
                user_data.get('rank', ''),
                'Да' if has_sub else 'Нет',
                'Да' if in_trial else 'Нет',
                len(user_data.get('referrals', [])),
                user_data.get('referral_earnings', 0),
                user_data.get('created_at', '')[:10],
                user_data.get('last_activity', '')[:10]
            ])
        
        # Отправляем файл
        from aiogram.types import BufferedInputFile
        
        csv_data = output.getvalue().encode('utf-8-sig')
        filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        await callback.message.answer_document(
            BufferedInputFile(csv_data, filename=filename),
            caption=f"📊 Экспорт пользователей ({len(users_list)} записей)"
        )
        
        try:
            await callback.answer("✅ Экспорт завершен")
        except:
            pass
        
    except Exception as e:
        logger.error(f"❌ Ошибка экспорта: {e}")
        try:
            await callback.answer("❌ Ошибка экспорта")
        except:
            pass

@dp.callback_query(F.data == "admin_users_back")
async def admin_users_back_handler(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку пользователей - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        if callback is None:
            return
        
        if not hasattr(callback, 'from_user') or callback.from_user is None:
            return
        
        if callback.from_user.id != config.ADMIN_ID:
            try:
                await callback.answer("⛔ Нет доступа")
            except:
                pass
            return
        
        if not hasattr(callback, 'message') or callback.message is None:
            try:
                await callback.answer("❌ Ошибка сообщения")
            except:
                pass
            return
        
        # Получаем всех пользователей заново
        users = await utils.get_all_users()
        users_list = []
        for user_id_str, user_data in users.items():
            try:
                users_list.append((int(user_id_str), user_data))
            except:
                continue
        
        # Сортируем по дате создания (новые первые)
        users_list.sort(
            key=lambda x: x[1].get('created_at', ''), 
            reverse=True
        )
        
        # Сохраняем в состояние
        await state.update_data(
            admin_users_list=users_list,
            admin_users_page=0
        )
        
        # Показываем первую страницу
        await show_users_page(callback, state, 0)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в admin_users_back_handler: {e}")
        try:
            await callback.answer("❌ Ошибка")
        except:
            pass

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

@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    """Отмена текущего действия"""
    try:
        if not message or not message.from_user:
            return
        
        current_state = await state.get_state()
        
        if current_state is None:
            await message.answer("❌ Нет активного действия для отмены")
            return
        
        await state.clear()
        
        user_id = message.from_user.id
        user_data = await utils.get_user(user_id)
        
        if user_data:
            await message.answer(
                "✅ Действие отменено",
                reply_markup=keyboards.get_main_menu(user_id)
            )
        else:
            await message.answer(
                "✅ Действие отменено",
                reply_markup=ReplyKeyboardRemove()
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка в cancel_command: {e}")
        await state.clear()


@dp.message(UserStates.waiting_for_invite)
async def process_invite_code(message: Message, state: FSMContext):
    """Обработка введенного инвайт-кода - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # 1. Проверяем message на None
        if message is None:
            logger.error("❌ process_invite_code: message is None")
            await state.clear()
            return
        
        # 2. Проверяем from_user на None
        if not hasattr(message, 'from_user') or message.from_user is None:
            logger.error("❌ process_invite_code: message.from_user is None")
            await state.clear()
            return
        
        user_id = message.from_user.id
        
        # 3. Получаем данные пользователя
        user_data = await utils.get_user(user_id)
        
        if not user_data:
            await message.answer("❌ Сначала зарегистрируйся через /start")
            await state.clear()
            return
        
        # 4. Проверка на команду отмены
        if hasattr(message, 'text') and message.text is not None:
            if message.text.lower() in ['/cancel', 'отмена', 'cancel']:
                await message.answer(
                    "❌ Ввод кода отменен",
                    reply_markup=keyboards.get_main_menu(user_id) if user_data else ReplyKeyboardRemove()
                )
                await state.clear()
                return
        else:
            await message.answer("❌ Пожалуйста, введите инвайт-код:")
            return
        
        # 5. Проверяем наличие текста
        if not message.text or message.text.strip() == "":
            await message.answer("❌ Пожалуйста, введите инвайт-код:")
            return
            
        invite_code = message.text.strip()
        
        # 6. Активируем код
        success, result = await utils.use_invite_code(invite_code, user_id)
        
        if success:
            invite_data = result
            days = invite_data.get('days', 30)
            updated_user_data = await utils.add_subscription_days(user_data, days)
            await utils.save_user(user_id, updated_user_data)
            
            await message.answer(
                f"✅ <b>Инвайт-код активирован!</b>\n\n"
                f"Вам добавлено <b>{days}</b> дней подписки.\n"
                f"Тип: {invite_data.get('name', 'Подписка')}\n\n"
                f"Теперь у вас есть доступ ко всем заданиям! 🎉",
                reply_markup=keyboards.get_main_menu(user_id)
            )
            
            # Отправляем задание
            try:
                current_day = updated_user_data.get('current_day', 0)
                next_day = current_day + 1
                
                if next_day == 0:
                    next_day = 1
                    
                task_id, task = await utils.get_task_by_day(next_day, updated_user_data.get('archetype', 'spartan'))
                
                if task:
                    task_message = (
                        f"📋 <b>Новое задание!</b>\n\n"
                        f"<b>День {next_day}/300</b>\n\n"
                        f"{task['text']}\n\n"
                        f"⏰ <b>Выполни задание до 23:59</b>\n\n"
                        f"<i>Отмечай выполнение кнопками ниже 👇</i>"
                    )
                    
                    await bot.send_message(
                        chat_id=user_id,
                        text=task_message,
                        reply_markup=keyboards.task_keyboard,
                        disable_web_page_preview=True
                    )
                    
                    updated_user_data['last_task_sent'] = datetime.now().isoformat()
                    updated_user_data['task_completed_today'] = False
                    await utils.save_user(user_id, updated_user_data)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка отправки задания: {e}")
            
            # Очищаем состояние после успешной активации
            await state.clear()
            
        else:
            error_message = result
            # Оставляем состояние активным для повторного ввода
            await message.answer(
                f"❌ <b>Не удалось активировать код</b>\n\n"
                f"{error_message}\n\n"
                f"Попробуйте другой код или введите /cancel для отмены"
            )
            # НЕ очищаем состояние здесь
        
        # Обновляем активность
        await utils.update_user_activity(user_id)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в process_invite_code: {e}", exc_info=True)
        
        # Безопасно отправляем сообщение об ошибке
        try:
            if message is not None and hasattr(message, 'from_user') and message.from_user is not None:
                user_id = message.from_user.id
                user_data = await utils.get_user(user_id)
                
                await message.answer(
                    "❌ Произошла ошибка. Попробуйте позже.",
                    reply_markup=keyboards.get_main_menu(user_id) if user_data else ReplyKeyboardRemove()
                )
        except:
            pass
        
        # Очищаем состояние
        await state.clear()

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
    
    # Получаем гендерные окончания
    gender = await utils.get_gender_ending(user_data)
    
    completed_tasks = user_data.get('completed_tasks', 0)
    current_rank_id = user_data.get('rank', 'putnik')
    current_rank = await utils.get_rank_info(current_rank_id)
    debts_count = await utils.get_current_debts_count(user_data)
    
    # Гендерные тексты
    if gender['person'] == 'Амазонка':
        your_rank = "Твой текущий ранг"
        your_challenge = "Твой вызов"
        your_progress = "Твоя прогрессия"
        current_debts = "Текущие долги"
    else:
        your_rank = "Твой текущий ранг"
        your_challenge = "Твой вызов"
        your_progress = "Твой прогресс"
        current_debts = "Текущие долги"
    
    message_text = (
        f"🏆 <b>{your_rank}: {current_rank.get('name', 'Путник')}</b>\n\n"
        f"<b>{your_challenge}:</b> {current_rank.get('description', '')}\n\n"
    )
    
    # Показываем привилегии текущего ранга
    privileges = current_rank.get('privileges', [])
    if privileges:
        message_text += "<b>🎁 Твои привилегии:</b>\n"
        for privilege in privileges:
            message_text += f"• {privilege}\n"
        message_text += "\n"
    
    message_text += f"<b>📊 {your_progress}:</b>\n"
    message_text += f"• Выполнено заданий: {completed_tasks}/300\n"
    message_text += f"• {current_debts}: {debts_count}\n"
    
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

# ========== скидка на праздник (тариф) 23 февраля 8 марта ==========

# ========== КОМАНДЫ ДЛЯ АДМИНА ==========

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramAPIError
)
# или просто импортируйте все
from aiogram import exceptions

# ========== ФУНКЦИИ ДЛЯ РАССЫЛОК ==========

async def send_feb23_promo_day1():
    """Отправка промо-сообщения на 22 февраля"""
    
    logger.info("🚀 Начинаю рассылку промо (22 февраля)...")
    
    users = await utils.get_all_users()
    
    message_text = (
        "<b>Спартанцы и Амазонки! 👋</b>\n\n"
        "В честь праздника дарим скидку 23 проце... НЕТ! <b>33 процента</b> на ПОЖИЗНЕННУЮ ПОДПИСКУ!\n\n"
        "🔥 Обычная цена: <s>3000 руб/год</s>\n"
        "🎁 По акции: <b>1990 руб/навсегда</b>\n\n"
        "⏳ Акция действует ТОЛЬКО 22, 23 и 24 февраля!\n\n"
        "Жми кнопку ниже, чтобы узнать подробности 👇"
    )
    
    keyboard = get_feb23_simple_keyboard()
    
    sent_count = 0
    error_count = 0
    blocked_count = 0
    not_found_count = 0
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            
            if not user_data or not isinstance(user_data, dict):
                continue
            
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            sent_count += 1
            
            if sent_count % 10 == 0:
                logger.info(f"📨 Отправлено {sent_count} сообщений...")
            
            await asyncio.sleep(0.05)
            
        except exceptions.TelegramForbiddenError:  # Вместо BotBlocked
            blocked_count += 1
            error_count += 1
            logger.debug(f"🚫 Пользователь {user_id_str} заблокировал бота")
            
        except exceptions.TelegramNotFound:  # Вместо ChatNotFound
            not_found_count += 1
            error_count += 1
            logger.debug(f"❓ Чат с пользователем {user_id_str} не найден")
            
        except exceptions.TelegramRetryAfter as e:
            # Превышение лимитов, нужно подождать
            logger.warning(f"⏳ Лимит, ждем {e.retry_after} сек")
            await asyncio.sleep(e.retry_after)
            
        except exceptions.TelegramAPIError as e:
            error_count += 1
            logger.error(f"❌ Ошибка API пользователю {user_id_str}: {e}")
            
        except Exception as e:
            error_count += 1
            logger.error(f"❌ Неизвестная ошибка пользователю {user_id_str}: {e}")
    
    logger.info(f"✅ Рассылка (22 фев) завершена. Отправлено: {sent_count}, Ошибок: {error_count} (блокировок: {blocked_count}, не найдено: {not_found_count})")
    return sent_count, error_count


async def send_feb23_promo_day2():
    """Отправка промо-сообщения на 23 февраля"""
    
    logger.info("🚀 Начинаю рассылку промо (23 февраля)...")
    
    users = await utils.get_all_users()
    
    message_text = (
        "🎖️ <b>С 23 ФЕВРАЛЯ, ЗАЩИТНИКИ!</b>\n\n"
        "<b>Спартанцы и Амазонки! 👋</b>\n\n"
        "В честь праздника дарим скидку <b>33%</b> на ПОЖИЗНЕННУЮ ПОДПИСКУ!\n\n"
        "🔥 Обычная цена: <s>3000 руб/год</s>\n"
        "🎁 По акции: <b>1990 руб/навсегда</b>\n\n"
        "СРОК ДО 24 ФЕВРАЛЯ ❗\n\n"
        "Успей купить безлимит 👇"
    )
    
    keyboard = get_feb23_simple_keyboard()
    
    sent_count = 0
    error_count = 0
    blocked_count = 0
    not_found_count = 0
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            
            if not user_data or not isinstance(user_data, dict):
                continue
            
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            sent_count += 1
            
            if sent_count % 10 == 0:
                logger.info(f"📨 Отправлено {sent_count} сообщений...")
            
            await asyncio.sleep(0.05)
            
        except exceptions.TelegramForbiddenError:
            blocked_count += 1
            error_count += 1
            logger.debug(f"🚫 Пользователь {user_id_str} заблокировал бота")
            
        except exceptions.TelegramNotFound:
            not_found_count += 1
            error_count += 1
            logger.debug(f"❓ Чат с пользователем {user_id_str} не найден")
            
        except exceptions.TelegramRetryAfter as e:
            logger.warning(f"⏳ Лимит, ждем {e.retry_after} сек")
            await asyncio.sleep(e.retry_after)
            
        except exceptions.TelegramAPIError as e:
            error_count += 1
            logger.error(f"❌ Ошибка API пользователю {user_id_str}: {e}")
            
        except Exception as e:
            error_count += 1
            logger.error(f"❌ Неизвестная ошибка пользователю {user_id_str}: {e}")
    
    logger.info(f"✅ Рассылка (23 фев) завершена. Отправлено: {sent_count}, Ошибок: {error_count}")
    return sent_count, error_count


async def send_feb23_promo_day3():
    """Отправка промо-сообщения на 24 февраля (последний день)"""
    
    logger.info("🚀 Начинаю рассылку промо (24 февраля, последний день)...")
    
    users = await utils.get_all_users()
    
    message_text = (
        "<b>Спартанцы и Амазонки! 👋</b>\n\n"
        "Спартанец ты или Амазонка – не важно, мы дарим Тебе скидку <b>33%</b> на ПОЖИЗНЕННУЮ ПОДПИСКУ!\n\n"
        "🔥 Обычная цена: <s>3000 руб/год</s>\n"
        "🎁 По акции: <b>1990 руб/навсегда</b>\n\n"
        "❗️❗️❗️❗️❗️❗️\n\n"
        "<b>СЕГОДНЯ ПОСЛЕДНИЙ ДЕНЬ❗️</b>\n\n"
        "Успей купить безлимит 👇"
    )
    
    keyboard = get_feb23_simple_keyboard()
    
    sent_count = 0
    error_count = 0
    blocked_count = 0
    not_found_count = 0
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            
            if not user_data or not isinstance(user_data, dict):
                continue
            
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            sent_count += 1
            
            if sent_count % 10 == 0:
                logger.info(f"📨 Отправлено {sent_count} сообщений...")
            
            await asyncio.sleep(0.05)
            
        except exceptions.TelegramForbiddenError:
            blocked_count += 1
            error_count += 1
            logger.debug(f"🚫 Пользователь {user_id_str} заблокировал бота")
            
        except exceptions.TelegramNotFound:
            not_found_count += 1
            error_count += 1
            logger.debug(f"❓ Чат с пользователем {user_id_str} не найден")
            
        except exceptions.TelegramRetryAfter as e:
            logger.warning(f"⏳ Лимит, ждем {e.retry_after} сек")
            await asyncio.sleep(e.retry_after)
            
        except exceptions.TelegramAPIError as e:
            error_count += 1
            logger.error(f"❌ Ошибка API пользователю {user_id_str}: {e}")
            
        except Exception as e:
            error_count += 1
            logger.error(f"❌ Неизвестная ошибка пользователю {user_id_str}: {e}")
    
    logger.info(f"✅ Рассылка (24 фев) завершена. Отправлено: {sent_count}, Ошибок: {error_count}")
    return sent_count, error_count


# ========== КОМАНДЫ ДЛЯ АДМИНА ==========

@dp.message(Command("send_feb23_22"))
async def cmd_send_feb23_22(message: Message):
    """Команда для отправки промо на 22 февраля"""
    
    if message is None or not hasattr(message, 'from_user') or message.from_user is None:
        logger.error("❌ cmd_send_feb23_22: message.from_user is None")
        return
    
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды")
        return
    
    await message.answer("🚀 Начинаю рассылку (22 февраля)...")
    sent, errors = await send_feb23_promo_day1()
    await message.answer(f"✅ Рассылка завершена!\n📨 Отправлено: {sent}\n❌ Ошибок: {errors}")


@dp.message(Command("send_feb23_23"))
async def cmd_send_feb23_23(message: Message):
    """Команда для отправки промо на 23 февраля"""
    
    if message is None or not hasattr(message, 'from_user') or message.from_user is None:
        logger.error("❌ cmd_send_feb23_23: message.from_user is None")
        return
    
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды")
        return
    
    await message.answer("🚀 Начинаю рассылку (23 февраля)...")
    sent, errors = await send_feb23_promo_day2()
    await message.answer(f"✅ Рассылка завершена!\n📨 Отправлено: {sent}\n❌ Ошибок: {errors}")


@dp.message(Command("send_feb23_24"))
async def cmd_send_feb23_24(message: Message):
    """Команда для отправки промо на 24 февраля (последний день)"""
    
    if message is None or not hasattr(message, 'from_user') or message.from_user is None:
        logger.error("❌ cmd_send_feb23_24: message.from_user is None")
        return
    
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды")
        return
    
    await message.answer("🚀 Начинаю рассылку (24 февраля, последний день)...")
    sent, errors = await send_feb23_promo_day3()
    await message.answer(f"✅ Рассылка завершена!\n📨 Отправлено: {sent}\n❌ Ошибок: {errors}")

def get_feb23_simple_keyboard():
    """Простая клавиатура для акции на 23 февраля"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔥 Купить пожизненную за 1990₽", 
                callback_data="tariff_forever"
            )],
            [InlineKeyboardButton(
                text="🎁 Подробнее об акции", 
                callback_data="feb23_simple_details"
            )]
        ]
    )
    return keyboard

@dp.callback_query(F.data == "feb23_simple_details")
async def feb23_simple_details(callback: CallbackQuery):
    """Подробности акции на 23 февраля"""
    
    if not callback or not callback.message:
        return
    
    message_text = (
        "🎖️ <b>АКЦИЯ НА 23 ФЕВРАЛЯ!</b>\n\n"
        "🔥 <b>Пожизненная подписка со скидкой 33%!</b>\n"
        "💰 Вместо 3000 руб. — всего 1990 руб.\n\n"
        
        "🎯 <b>Что дает пожизненная подписка:</b>\n"
        "• Доступ ко всем 300 заданиям НАВСЕГДА\n"
        "• Проходи челлендж в своём темпе (хоть год, хоть два)\n"
        "• Все будущие обновления бесплатно\n\n"
        
        "⏳ Акция действует ТОЛЬКО 22, 23 и 24 февраля!\n\n"
        "<b>Жми кнопку ниже для оплаты</b> 👇"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔥 Оплатить 1990 руб.", 
                callback_data="tariff_forever"
            )]
        ]
    )
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await callback.answer()

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
# В функции main() добавляем:
async def main():
    """Главная функция запуска бота"""
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА '300 ПИНКОВ'")
    logger.info("=" * 50)
    
    # Получаем информацию о боте
    try:
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот: @{bot_info.username}")
        logger.info(f"🆔 ID бота: {bot_info.id}")
        logger.info(f"👤 Имя бота: {bot_info.first_name}")
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о боте: {e}")
    
    # Проверяем конфигурацию
    logger.info("🔧 Проверка конфигурации...")
    if not config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен!")
        return
    
    if not config.ADMIN_ID:
        logger.warning("⚠️ ADMIN_ID не установлен, админские функции недоступны")
    
    logger.info("✅ Конфигурация проверена")
    
    # Проверяем файлы данных
    logger.info("📁 Проверка файлов данных...")
    try:
        # Проверяем существование файлов
        import os
        required_files = [
            config.USERS_FILE,
            config.PAYMENTS_FILE,
            config.WITHDRAWALS_FILE,
            config.INVITE_CODES_FILE
        ]
        
        for file in required_files:
            if not os.path.exists(file):
                # Создаем пустые файлы если их нет
                await utils.write_json(file, {})
                logger.info(f"📄 Создан файл: {file}")
            else:
                logger.info(f"✅ Файл существует: {file}")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки файлов: {e}")
    
    # Инициализируем планировщик
    logger.info("📅 Инициализация планировщика задач...")
    
    try:
        # ========== ОСНОВНЫЕ ЗАДАЧИ РАССЫЛКИ ==========
        
        # 1. Ежедневная рассылка заданий в 9:00
        scheduler.add_job(
            send_daily_tasks,
            trigger=CronTrigger(
                hour=config.TASK_TIME_HOUR,
                minute=config.TASK_TIME_MINUTE,
                timezone=config.TIMEZONE
            ),
            id="daily_tasks",
            name="Ежедневная рассылка заданий",
            misfire_grace_time=300,  # 5 минут на выполнение если пропустили
            coalesce=True  # Объединять пропущенные выполнения
        )
        logger.info(f"✅ Задача: Рассылка заданий в {config.TASK_TIME_HOUR:02d}:{config.TASK_TIME_MINUTE:02d}")
        
        # 2. Напоминания в 18:30
        scheduler.add_job(
            send_reminders,
            trigger=CronTrigger(
                hour=config.REMINDER_TIME_HOUR,
                minute=config.REMINDER_TIME_MINUTE,
                timezone=config.TIMEZONE
            ),
            id="reminders",
            name="Вечерние напоминания",
            misfire_grace_time=300
        )
        logger.info(f"✅ Задача: Напоминания в {config.REMINDER_TIME_HOUR:02d}:{config.REMINDER_TIME_MINUTE:02d}")
        
        # 3. Полночный сброс в 00:00
        scheduler.add_job(
            check_midnight_reset,
            trigger=CronTrigger(
                hour=0, minute=0,
                timezone=config.TIMEZONE
            ),
            id="midnight_reset",
            name="Полночный сброс и блокировка",
            misfire_grace_time=600  # 10 минут на выполнение
        )
        logger.info("✅ Задача: Полночный сброс в 00:00")
        
        # ========== УВЕДОМЛЕНИЯ О ПОДПИСКАХ ==========
        
        # 4. Умные уведомления о подписках (каждый день в 11:00)
        scheduler.add_job(
            SubscriptionNotifications.check_all_users_for_subscription_notifications,
            trigger=CronTrigger(
                hour=19, minute=15,
                timezone=config.TIMEZONE
            ),
            id="smart_subscription_notifications",
            name="Умные уведомления о подписках",
            misfire_grace_time=300
        )
        logger.info("✅ Задача: Умные уведомления о подписках в 11:00")
        
        # 5. Быстрая проверка подписок (каждые 6 часов)
        scheduler.add_job(
            lambda: SubscriptionNotifications.check_all_users_for_subscription_notifications(),
            trigger=CronTrigger(
                hour="*/6",  # Каждые 6 часов
                minute=30,
                timezone=config.TIMEZONE
            ),
            id="quick_subscription_check",
            name="Быстрая проверка подписок",
            misfire_grace_time=300
        )
        logger.info("✅ Задача: Быстрая проверка подписок каждые 6 часов")
        
        # ========== АВТОМАТИЧЕСКИЕ ПРОЦЕССЫ ==========
        
        # 6. Проверка пробного периода в 10:00
        if 'check_trial_expiry' in globals():
            scheduler.add_job(
                check_trial_expiry,
                trigger=CronTrigger(
                    hour=19, minute=3,
                    timezone=config.TIMEZONE
                ),
                id="trial_expiry_check",
                name="Проверка пробного периода",
                misfire_grace_time=300
            )
            logger.info("✅ Задача: Проверка пробного периода в 10:00")
        
        # 7. Авто-пропуск просроченных заданий (каждые 6 часов)
        if 'check_and_auto_skip_expired_blocks' in globals():
            scheduler.add_job(
                check_and_auto_skip_expired_blocks,
                trigger=CronTrigger(
                    hour="*/6",  # Каждые 6 часов
                    minute=0,
                    timezone=config.TIMEZONE
                ),
                id="auto_skip_check",
                name="Авто-пропуск просроченных заданий",
                misfire_grace_time=300
            )
            logger.info("✅ Задача: Авто-пропуск просроченных заданий каждые 6 часов")
        
        # 8. Уведомления неактивным пользователям в 12:00
        if 'simple_inactive_users_check' in globals():
            scheduler.add_job(
                simple_inactive_users_check,
                trigger=CronTrigger(
                    hour=19, minute=14,
                    timezone=config.TIMEZONE
                ),
                id="inactive_users_notifications",
                name="Уведомления неактивным пользователям",
                misfire_grace_time=300
            )
            logger.info("✅ Задача: Уведомления неактивным пользователям в 12:00")
        
        # Запускаем все задачи сразу для тестирования при старте
        logger.info("🔄 Запуск тестовых задач при старте...")
        
        # Немедленный запуск тестовых задач (асинхронно, не блокируя старт)
        asyncio.create_task(run_initial_checks())
        
        # Запускаем планировщик
        scheduler.start()
        logger.info("✅ Планировщик запущен")
        logger.info(f"📊 Всего задач: {len(scheduler.get_jobs())}")
        
        # Выводим расписание
        logger.info("📅 Расписание задач:")
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            if next_run:
                next_run_str = next_run.astimezone(pytz.timezone(config.TIMEZONE)).strftime("%d.%m.%Y %H:%M")
                logger.info(f"  • {job.name}: следующее выполнение в {next_run_str}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации планировщика: {e}")
        return
    
    # Запускаем бота
    try:
        logger.info("🤖 Запускаем бота...")
        logger.info("=" * 50)
        
        # Показываем информацию о доступных командах
        logger.info("🎮 Доступные команды для админа:")
        logger.info("  • /start - начать/перезапустить")
        logger.info("  • /ref - реферальная ссылка")
        logger.info("  • /rank - текущий ранг")
        logger.info("  • /refstats - статистика рефералов")
        logger.info("  • /check_subscription - статус подписки")
        logger.info("  • /checkme - отладка данных")
        logger.info("  • /debug_ref - отладка реферальной системы")
        logger.info("  • /test_ranks - тест системы рангов")
        logger.info("  • /reset_test_rank - сброс тестового режима")
        logger.info("  • /reset_me - полный сброс пользователя")
        logger.info("  • /force_reset USER_ID - принудительный сброс (админ)")
        logger.info("=" * 50)
        
        # Запускаем поллинг бота
        await dp.start_polling(bot, skip_updates=True)  # skip_updates=True чтобы игнорировать сообщения пока бот был оффлайн
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}", exc_info=True)
    finally:
        # Останавливаем планировщик при завершении
        logger.info("🛑 Останавливаем планировщик...")
        scheduler.shutdown()
        logger.info("👋 Бот завершил работу")


async def run_initial_checks():
    """Запуск первоначальных проверок при старте"""
    try:
        logger.info("🔍 Запуск первоначальных проверок...")
        
        # 1. Проверка пользователей
        users = await utils.get_all_users()
        logger.info(f"👥 Всего пользователей в системе: {len(users)}")
        
        # 2. Быстрая проверка подписок
        await SubscriptionNotifications.check_all_users_for_subscription_notifications()
        
        # 3. Проверка блокировок
        if 'check_and_auto_skip_expired_blocks' in globals():
            await check_and_auto_skip_expired_blocks()
        
        logger.info("✅ Первоначальные проверки завершены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при первоначальных проверках: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("👋 Работа бота завершена")
