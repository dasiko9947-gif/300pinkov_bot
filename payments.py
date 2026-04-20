# payments.py
import json
import aiohttp
import base64
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import config

logger = logging.getLogger(__name__)


async def create_yookassa_payment(amount: float, description: str, user_id: int, tariff_id: str) -> Optional[Dict[str, Any]]:
    """
    Создает платеж в ЮKassa
    
    Args:
        amount: сумма платежа
        description: описание платежа
        user_id: ID пользователя
        tariff_id: ID тарифа
    
    Returns:
        dict: данные платежа или None при ошибке
    """
    try:
        auth = base64.b64encode(
            f"{config.YOOKASSA_SHOP_ID}:{config.YOOKASSA_SECRET_KEY}".encode()
        ).decode()
        
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/json',
            'Idempotence-Key': f"{datetime.now().timestamp()}_{user_id}"
        }
        
        payment_data = {
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
                "user_id": str(user_id),
                "tariff_id": tariff_id
            }
        }
        
        url = 'https://api.yookassa.ru/v3/payments'
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payment_data, headers=headers) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    
                    # Сохраняем информацию о платеже в локальный файл
                    await save_payment_to_file({
                        'payment_id': data['id'],
                        'user_id': user_id,
                        'tariff_id': tariff_id,
                        'amount': amount,
                        'description': description,
                        'status': data.get('status'),
                        'confirmation_url': data['confirmation']['confirmation_url'],
                        'created_at': datetime.now().isoformat()
                    })
                    
                    return {
                        'payment_id': data['id'],
                        'confirmation_url': data['confirmation']['confirmation_url'],
                        'status': data.get('status')
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка создания платежа: {response.status} - {error_text}")
                    return None
                    
    except Exception as e:
        logger.error(f"❌ Ошибка в create_yookassa_payment: {e}")
        return None

async def update_payment_stage(payment_id: str, stage_num: int) -> bool:
    """
    Обновляет данные платежа, добавляя информацию о выбранном этапе
    
    Args:
        payment_id: ID платежа в системе ЮKassa
        stage_num: выбранный пользователем этап (1-10)
    
    Returns:
        bool: успешно ли обновлено
    """
    try:
        payments = await read_json(config.PAYMENTS_FILE)
        
        if not payments or payment_id not in payments:
            logger.warning(f"⚠️ Платеж {payment_id} не найден для обновления этапа")
            return False
        
        # Добавляем информацию об этапе
        payments[payment_id]['selected_stage'] = stage_num
        
        # Сохраняем
        await write_json(config.PAYMENTS_FILE, payments)
        
        logger.info(f"✅ Добавлен этап {stage_num} к платежу {payment_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления этапа платежа: {e}")
        return False

async def save_payment_to_file(payment_data: dict) -> None:
    """Сохраняет информацию о платеже в файл"""
    try:
        payments = await read_json(config.PAYMENTS_FILE)
        if not payments:
            payments = {}
        
        payments[payment_data['payment_id']] = payment_data
        await write_json(config.PAYMENTS_FILE, payments)
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения платежа: {e}")


async def get_payment_data(payment_id: str) -> Optional[Dict[str, Any]]:
    """Получает данные платежа из локального файла"""
    try:
        payments = await read_json(config.PAYMENTS_FILE)
        if not payments:
            return None
        
        return payments.get(payment_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения данных платежа: {e}")
        return None


async def update_payment_status(payment_id: str, status: str) -> bool:
    """Обновляет статус платежа в локальном файле"""
    try:
        payments = await read_json(config.PAYMENTS_FILE)
        if not payments or payment_id not in payments:
            return False
        
        payments[payment_id]['status'] = status
        await write_json(config.PAYMENTS_FILE, payments)
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статуса платежа: {e}")
        return False


async def check_payment_status(payment_id: str) -> Optional[str]:
    """
    Проверяет статус платежа в ЮKassa
    
    Args:
        payment_id: ID платежа
    
    Returns:
        str: статус платежа ('succeeded', 'pending', 'canceled') или None при ошибке
    """
    try:
        auth = base64.b64encode(
            f"{config.YOOKASSA_SHOP_ID}:{config.YOOKASSA_SECRET_KEY}".encode()
        ).decode()
        
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/json'
        }
        
        url = f'https://api.yookassa.ru/v3/payments/{payment_id}'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    status = data.get('status')
                    
                    # Обновляем статус в локальном файле
                    await update_payment_status(payment_id, status)
                    
                    return status
                else:
                    logger.error(f"❌ Ошибка проверки платежа {payment_id}: {response.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"❌ Ошибка в check_payment_status: {e}")
        return None


async def read_json(file_path):
    """Асинхронно читает JSON файл"""
    try:
        import aiofiles
        import json
        from pathlib import Path
        
        file_path = Path(file_path)
        
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
        import aiofiles
        import json
        from pathlib import Path
        
        file_path = Path(file_path)
        
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"Error writing {file_path}: {e}")