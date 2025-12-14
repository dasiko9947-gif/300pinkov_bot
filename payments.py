import asyncio
import uuid
from yookassa import Payment, Configuration
import config
from datetime import datetime

# Настройка ЮKassa
Configuration.account_id = config.YOOKASSA_SHOP_ID
Configuration.secret_key = config.YOOKASSA_SECRET_KEY

async def create_yookassa_payment(amount, description, user_id, tariff_id):
    """Создает платеж в ЮKassa с улучшенной обработкой ошибок"""
    try:
        # Генерируем уникальный ID платежа
        payment_id = str(uuid.uuid4())
        
        print(f"🔄 Создаем платеж: {amount} руб., пользователь {user_id}, тариф {tariff_id}")
        
        # Создаем платеж
        payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": config.YOOKASSA_RETURN_URL
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": user_id,
                "tariff_id": tariff_id,
                "payment_id": payment_id
            },
            "save_payment_method": False
        })
        
        print(f"✅ Платеж создан в ЮKassa: {payment.id}")
        
        # ПРОВЕРЯЕМ, ЧТО confirmation_url СУЩЕСТВУЕТ
        if not hasattr(payment, 'confirmation') or not payment.confirmation:
            print("❌ Ошибка: нет объекта confirmation")
            return None
            
        if not hasattr(payment.confirmation, 'confirmation_url') or not payment.confirmation.confirmation_url:
            print("❌ Ошибка: нет confirmation_url")
            return None
            
        confirmation_url = payment.confirmation.confirmation_url
        print(f"🔗 URL подтверждения: {confirmation_url}")
        
        # Сохраняем информацию о платеже
        payment_data = {
            'payment_id': payment_id,
            'yookassa_id': payment.id,
            'user_id': user_id,
            'tariff_id': tariff_id,
            'amount': amount,
            'description': description,
            'status': payment.status,
            'created_at': datetime.now().isoformat(),
            'confirmation_url': confirmation_url
        }
        
        await save_payment_data(payment_data)
        print(f"✅ Данные платежа сохранены: {payment_id}")
        
        return payment_data
        
    except Exception as e:
        print(f"❌ Критическая ошибка создания платежа: {e}")
        import traceback
        traceback.print_exc()
        return None

async def save_payment_data(payment_data):
    """Сохраняет данные платежа"""
    import utils
    payments = await utils.read_json(config.PAYMENTS_FILE)
    payments[payment_data['payment_id']] = payment_data
    await utils.write_json(config.PAYMENTS_FILE, payments)

async def get_payment_data(payment_id):
    """Получает данные платежа"""
    import utils
    payments = await utils.read_json(config.PAYMENTS_FILE)
    return payments.get(payment_id)

async def update_payment_status(payment_id, status):
    """Обновляет статус платежа"""
    import utils
    payments = await utils.read_json(config.PAYMENTS_FILE)
    if payment_id in payments:
        payments[payment_id]['status'] = status
        payments[payment_id]['updated_at'] = datetime.now().isoformat()
        await utils.write_json(config.PAYMENTS_FILE, payments)

async def check_payment_status(payment_id):
    """Проверяет статус платежа в ЮKassa"""
    try:
        payment_data = await get_payment_data(payment_id)
        if not payment_data:
            print(f"❌ Платеж {payment_id} не найден в базе")
            return None
            
        # Получаем статус из ЮKassa
        payment = Payment.find_one(payment_data['yookassa_id'])
        if not payment:
            print(f"❌ Платеж {payment_data['yookassa_id']} не найден в ЮKassa")
            return None
            
        print(f"✅ Статус платежа {payment_id}: {payment.status}")
        return payment.status
        
    except Exception as e:
        print(f"❌ Ошибка проверки статуса платежа {payment_id}: {e}")
        return None