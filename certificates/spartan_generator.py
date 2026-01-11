import os
import base64
from datetime import datetime, timedelta
from pathlib import Path

class SpartanCertificateGenerator:
    def __init__(self, output_dir="certificates/generated"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir = Path("images")
        
    def format_tariff_description(self, tariff_data):
        """Форматирует описание тарифа"""
        name = tariff_data['name']
        days = tariff_data['days']
        
        if 'месячн' in name.lower():
            return "Месячная подписка на 30 дней"
        elif 'годов' in name.lower():
            return "Годовая подписка на 365 дней"
        elif 'парн' in name.lower():
            return "Парная годовая подписка"
        else:
            return f"Подписка на {days} дней"
    
    def get_spartan_image_base64(self):
        """Получает изображение спартанца в base64"""
        spartan_image_path = self.image_dir / "spartan.jpg"
        
        # Проверяем наличие файла с разными расширениями
        if not spartan_image_path.exists():
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                alternative_path = self.image_dir / f"spartan{ext}"
                if alternative_path.exists():
                    spartan_image_path = alternative_path
                    break
        
        if spartan_image_path.exists():
            try:
                with open(spartan_image_path, 'rb') as img_file:
                    return base64.b64encode(img_file.read()).decode('utf-8')
            except:
                return None
        return None
    
    def generate_certificate(self, invite_code, tariff_data, buyer_data, config):
        """Генерирует спартанский сертификат формата А4 с адаптацией под мобильные"""
        expiry_date = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
        
        # Форматируем названия
        tariff_description = self.format_tariff_description(tariff_data)
        
        bot_username = getattr(config, 'BOT_USERNAME', 'pinkov300_bot')
        bot_link = f"https://t.me/{bot_username}"
        certificate_id = f"CERT-{invite_code[:8].upper()}"
        
        # QR-код для перехода в бота
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={bot_link}"
        
        # Получаем изображение спартанца
        spartan_image_base64 = self.get_spartan_image_base64()
        
        html_content = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>Подарочный сертификат «300 ПИНКОВ»</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Roboto:wght@300;400;500&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }}
        
        :root {{
            --primary-red: #d40000;
            --light-red: #ff3333;
            --dark-red: #990000;
            --background: #0a0a0a;
            --text: #ffffff;
            --muted: #cccccc;
            --green: #4CAF50;
        }}
        
        body {{
            font-family: 'Roboto', sans-serif;
            background: var(--background);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 10px;
            -webkit-text-size-adjust: 100%;
            -webkit-font-smoothing: antialiased;
        }}
        
        /* Мобильная версия по умолчанию */
        .certificate-container {{
            width: 100%;
            max-width: 600px;
            min-height: auto;
            position: relative;
            background: var(--background);
            border: 2px solid var(--primary-red);
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(212, 0, 0, 0.2);
            margin: 0 auto;
        }}
        
        /* Десктоп версия (А4) */
        @media (min-width: 768px) and (orientation: landscape) {{
            .certificate-container {{
                width: 210mm;
                height: 297mm;
                max-width: 210mm;
                border: 3px solid var(--primary-red);
                border-radius: 0;
                box-shadow: 0 15px 40px rgba(212, 0, 0, 0.25);
            }}
            
            body {{
                padding: 20px;
            }}
        }}
        
        /* Фоновое изображение спартанца */
        .spartan-background {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0.2;
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            z-index: 1;
            pointer-events: none;
        }}
        
        @media (min-width: 768px) {{
            .spartan-background {{
                opacity: 0.25;
            }}
        }}
        
        .certificate-content {{
            position: relative;
            z-index: 2;
            height: 100%;
            padding: 20px;
            display: flex;
            flex-direction: column;
        }}
        
        @media (min-width: 768px) {{
            .certificate-content {{
                padding: 15mm;
            }}
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid rgba(212, 0, 0, 0.3);
        }}
        
        @media (min-width: 768px) {{
            .header {{
                margin-bottom: 8mm;
            }}
        }}
        
        .main-title {{
            font-family: 'Cinzel', serif;
            font-size: 28px;
            font-weight: 900;
            color: var(--light-red);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 8px;
            text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.8);
            line-height: 1.2;
        }}
        
        @media (min-width: 768px) {{
            .main-title {{
                font-size: 48px;
                letter-spacing: 4px;
                margin-bottom: 5px;
            }}
        }}
        
        .subtitle {{
            font-family: 'Cinzel', serif;
            font-size: 16px;
            color: #ff6666;
            letter-spacing: 1px;
            line-height: 1.3;
        }}
        
        @media (min-width: 768px) {{
            .subtitle {{
                font-size: 22px;
                letter-spacing: 2px;
            }}
        }}
        
        .bot-description {{
            text-align: center;
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(212, 0, 0, 0.1);
            border-radius: 10px;
            border-left: 3px solid var(--primary-red);
            font-size: 14px;
            line-height: 1.4;
        }}
        
        @media (min-width: 768px) {{
            .bot-description {{
                margin-bottom: 8mm;
                padding: 5mm;
                font-size: 16px;
                line-height: 1.5;
            }}
        }}
        
        .content-wrapper {{
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin-bottom: 20px;
            flex: 1;
        }}
        
        @media (min-width: 768px) {{
            .content-wrapper {{
                flex-direction: row;
                gap: 12mm;
                margin-bottom: 8mm;
            }}
        }}
        
        .left-section, .right-section {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        
        @media (min-width: 768px) {{
            .left-section {{
                flex: 3;
                gap: 8mm;
            }}
            
            .right-section {{
                flex: 2;
                gap: 8mm;
            }}
        }}
        
        .gift-card {{
            background: rgba(212, 0, 0, 0.15);
            border: 2px solid rgba(212, 0, 0, 0.5);
            padding: 20px;
            border-radius: 12px;
        }}
        
        @media (min-width: 768px) {{
            .gift-card {{
                padding: 6mm;
                border-radius: 4mm;
            }}
        }}
        
        .gift-card h3 {{
            font-family: 'Cinzel', serif;
            color: var(--light-red);
            font-size: 20px;
            margin-bottom: 15px;
            text-align: center;
        }}
        
        @media (min-width: 768px) {{
            .gift-card h3 {{
                font-size: 22px;
                margin-bottom: 4mm;
            }}
        }}
        
        .subscription-type {{
            background: rgba(212, 0, 0, 0.25);
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            text-align: center;
            font-size: 16px;
            font-weight: 500;
            color: var(--text);
            line-height: 1.3;
        }}
        
        @media (min-width: 768px) {{
            .subscription-type {{
                padding: 4mm;
                border-radius: 3mm;
                margin: 4mm 0;
                font-size: 18px;
            }}
        }}
        
        .detail-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
            margin-top: 15px;
        }}
        
        @media (min-width: 768px) {{
            .detail-grid {{
                grid-template-columns: 1fr 1fr;
                gap: 3mm;
                margin-top: 4mm;
            }}
        }}
        
        .detail-item {{
            background: rgba(0, 0, 0, 0.4);
            padding: 12px;
            border-radius: 8px;
            border: 1px solid rgba(212, 0, 0, 0.3);
            text-align: center;
        }}
        
        @media (min-width: 768px) {{
            .detail-item {{
                padding: 3mm;
                border-radius: 2mm;
            }}
        }}
        
        .detail-label {{
            color: #ff9999;
            font-size: 12px;
            margin-bottom: 5px;
        }}
        
        .detail-value {{
            color: var(--text);
            font-weight: 500;
            font-size: 14px;
        }}
        
        @media (min-width: 768px) {{
            .detail-value {{
                font-size: 16px;
            }}
        }}
        
        .instructions {{
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            border: 1px solid rgba(212, 0, 0, 0.3);
        }}
        
        @media (min-width: 768px) {{
            .instructions {{
                padding: 5mm;
                border-radius: 3mm;
                margin-top: 4mm;
            }}
        }}
        
        .instructions h4 {{
            color: var(--light-red);
            font-size: 16px;
            margin-bottom: 10px;
            text-align: center;
        }}
        
        .instruction-steps {{
            color: #cccccc;
            font-size: 13px;
            line-height: 1.5;
        }}
        
        @media (min-width: 768px) {{
            .instruction-steps {{
                font-size: 14px;
                line-height: 1.6;
            }}
        }}
        
        .instruction-steps ol {{
            padding-left: 20px;
            margin: 10px 0;
        }}
        
        .instruction-steps li {{
            margin-bottom: 8px;
        }}
        
        @media (min-width: 768px) {{
            .instruction-steps li {{
                margin-bottom: 2mm;
            }}
        }}
        
        .code-card {{
            background: rgba(0, 0, 0, 0.5);
            border: 2px solid var(--primary-red);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }}
        
        @media (min-width: 768px) {{
            .code-card {{
                padding: 6mm;
                border: 3px solid var(--primary-red);
                border-radius: 4mm;
            }}
        }}
        
        .code-title {{
            color: #ff6666;
            font-size: 16px;
            margin-bottom: 15px;
            text-transform: uppercase;
        }}
        
        @media (min-width: 768px) {{
            .code-title {{
                font-size: 18px;
                margin-bottom: 4mm;
            }}
        }}
        
        .invite-code {{
            font-family: 'Courier New', monospace;
            font-size: 24px;
            font-weight: bold;
            color: var(--text);
            background: rgba(0, 0, 0, 0.6);
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border: 2px solid rgba(212, 0, 0, 0.5);
            letter-spacing: 2px;
            word-break: break-all;
            word-wrap: break-word;
            overflow-wrap: break-word;
            line-height: 1.3;
        }}
        
        @media (min-width: 768px) {{
            .invite-code {{
                font-size: 32px;
                padding: 4mm;
                border-radius: 3mm;
                margin: 4mm 0;
                letter-spacing: 3px;
                word-break: keep-all;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
        }}
        
        .copy-button {{
            background: transparent;
            color: var(--light-red);
            border: 2px solid var(--light-red);
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 10px;
            transition: all 0.3s;
            font-size: 14px;
            width: 100%;
            max-width: 250px;
            margin-left: auto;
            margin-right: auto;
            display: block;
            touch-action: manipulation;
        }}
        
        .copy-button:active {{
            transform: scale(0.98);
            background: var(--light-red);
            color: var(--background);
        }}
        
        @media (min-width: 768px) {{
            .copy-button {{
                padding: 8px 20px;
                margin-top: 3mm;
                width: auto;
                display: inline-block;
            }}
            
            .copy-button:hover {{
                background: var(--light-red);
                color: var(--background);
                transform: translateY(-2px);
            }}
            
            .copy-button:active {{
                transform: scale(0.98);
            }}
        }}
        
        .validity-info {{
            color: #ff9999;
            font-size: 13px;
            margin-top: 10px;
            line-height: 1.4;
        }}
        
        @media (min-width: 768px) {{
            .validity-info {{
                font-size: 14px;
                margin-top: 3mm;
            }}
        }}
        
        .qr-card {{
            background: rgba(255, 255, 255, 0.05);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }}
        
        @media (min-width: 768px) {{
            .qr-card {{
                padding: 6mm;
                border-radius: 4mm;
            }}
        }}
        
        .qr-title {{
            color: #ff6666;
            font-size: 16px;
            margin-bottom: 10px;
        }}
        
        @media (min-width: 768px) {{
            .qr-title {{
                font-size: 16px;
                margin-bottom: 3mm;
            }}
        }}
        
        .qr-container {{
            margin: 15px auto;
            width: 180px;
            height: 180px;
            background: white;
            padding: 10px;
            border-radius: 10px;
            max-width: 100%;
        }}
        
        @media (min-width: 768px) {{
            .qr-container {{
                width: 140px;
                height: 140px;
                margin: 3mm auto;
                padding: 2mm;
                border-radius: 2mm;
            }}
        }}
        
        .qr-container img {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        
        .bot-reference {{
            color: var(--muted);
            font-size: 14px;
            margin-top: 10px;
            margin-bottom: 15px;
        }}
        
        /* Кнопка перехода в бота */
        .telegram-button {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            background: linear-gradient(135deg, #0088cc, #00aced);
            color: white;
            text-decoration: none;
            padding: 12px 25px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 16px;
            transition: all 0.3s;
            margin-top: 10px;
            width: 100%;
            max-width: 280px;
            margin-left: auto;
            margin-right: auto;
            border: none;
            cursor: pointer;
            touch-action: manipulation;
        }}
        
        .telegram-button i {{
            font-size: 18px;
        }}
        
        .telegram-button:active {{
            transform: scale(0.98);
            background: linear-gradient(135deg, #0077b5, #0099d6);
        }}
        
        @media (min-width: 768px) {{
            .telegram-button {{
                width: auto;
                max-width: none;
                padding: 10px 25px;
            }}
            
            .telegram-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 136, 204, 0.4);
                background: linear-gradient(135deg, #0099e6, #00bfff);
            }}
            
            .telegram-button:active {{
                transform: scale(0.98);
            }}
        }}
        
        .footer {{
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid rgba(212, 0, 0, 0.3);
            color: #999;
            font-size: 12px;
        }}
        
        @media (min-width: 768px) {{
            .footer {{
                padding-top: 5mm;
                font-size: 12px;
            }}
        }}
        
        .actions {{
            margin-top: 20px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            align-items: center;
        }}
        
        @media (min-width: 768px) {{
            .actions {{
                margin-top: 5mm;
                flex-direction: row;
                justify-content: center;
                gap: 10mm;
            }}
        }}
        
        .print-button {{
            background: linear-gradient(135deg, var(--primary-red), var(--light-red));
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            border: none;
            font-weight: bold;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
            width: 100%;
            max-width: 300px;
            touch-action: manipulation;
        }}
        
        .print-button:active {{
            transform: scale(0.98);
        }}
        
        @media (min-width: 768px) {{
            .print-button {{
                padding: 10px 25px;
                width: auto;
                max-width: none;
            }}
            
            .print-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(212, 0, 0, 0.4);
            }}
            
            .print-button:active {{
                transform: scale(0.98);
            }}
        }}
        
        /* Настройки для печати */
        @media print {{
            @page {{
                size: A4;
                margin: 0;
            }}
            
            body {{
                padding: 0 !important;
                margin: 0 !important;
                background: white !important;
                width: 210mm !important;
                height: 297mm !important;
            }}
            
            .certificate-container {{
                width: 210mm !important;
                height: 297mm !important;
                max-width: 210mm !important;
                border: none !important;
                margin: 0 !important;
                border-radius: 0 !important;
                page-break-inside: avoid;
                box-shadow: none !important;
            }}
            
            .certificate-content {{
                padding: 15mm !important;
            }}
            
            .print-button, .copy-button, .telegram-button {{
                display: none !important;
            }}
            
            .spartan-background {{
                opacity: 0.15 !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}
            
            /* Убедимся, что все цвета печатаются */
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}
            
            .invite-code {{
                white-space: nowrap !important;
                overflow: visible !important;
                text-overflow: clip !important;
                font-size: 28px !important;
            }}
        }}
        
        /* Особенности для очень маленьких экранов */
        @media (max-width: 360px) {{
            .main-title {{
                font-size: 24px;
            }}
            
            .subtitle {{
                font-size: 14px;
            }}
            
            .invite-code {{
                font-size: 20px;
                padding: 12px;
            }}
            
            .qr-container {{
                width: 150px;
                height: 150px;
            }}
            
            .bot-description {{
                font-size: 13px;
                padding: 12px;
            }}
            
            .telegram-button {{
                padding: 10px 20px;
                font-size: 14px;
            }}
        }}
        
        /* Планшеты в портретной ориентации */
        @media (min-width: 600px) and (max-width: 767px) {{
            .certificate-container {{
                max-width: 500px;
            }}
            
            .main-title {{
                font-size: 32px;
            }}
            
            .invite-code {{
                font-size: 28px;
            }}
            
            .qr-container {{
                width: 200px;
                height: 200px;
            }}
        }}
        
        /* Планшеты в альбомной ориентации */
        @media (min-width: 768px) and (max-width: 1023px) and (orientation: landscape) {{
            .certificate-container {{
                width: 90%;
                height: auto;
                max-width: 800px;
            }}
            
            .content-wrapper {{
                flex-direction: row;
            }}
            
            .invite-code {{
                font-size: 28px;
                white-space: normal;
                word-break: break-all;
            }}
        }}
        
        /* Улучшенная поддержка iOS */
        @supports (-webkit-touch-callout: none) {{
            .copy-button, .print-button, .telegram-button {{
                -webkit-appearance: none;
            }}
            
            .certificate-container {{
                -webkit-overflow-scrolling: touch;
            }}
        }}
    </style>
</head>
<body>
    <div class="certificate-container">
        <!-- Фоновое изображение спартанца -->
        <div class="spartan-background" style="background-image: url('data:image/jpeg;base64,{spartan_image_base64 if spartan_image_base64 else 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='}')"></div>
        
        <div class="certificate-content">
            <header class="header">
                <h1 class="main-title">Подарочный сертификат</h1>
                <div class="subtitle">Челлендж «300 ПИНКОВ»</div>
            </header>
            
            <div class="bot-description">
                <p>Бот для развития силы воли и дисциплины. Ежедневные задания, которые меняют привычки и мышление. 300 дней непрерывного роста.</p>
            </div>
            
            <div class="content-wrapper">
                <div class="left-section">
                    <div class="gift-card">
                        <h3>🎁 ДЕТАЛИ ПОДАРКА</h3>
                        <div class="subscription-type">
                            {tariff_description}
                        </div>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <div class="detail-label">Срок подписки:</div>
                                <div class="detail-value">{tariff_data['days']} дней</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Действует до:</div>
                                <div class="detail-value">{expiry_date}</div>
                            </div>
                        </div>
                        
                        <div class="instructions">
                            <h4>📋 КРАТКАЯ ИНСТРУКЦИЯ</h4>
                            <div class="instruction-steps">
                                <ol>
                                    <li>Перейдите в бота @{bot_username}</li>
                                    <li>Нажмите START для регистрации</li>
                                    <li>Выберите «Сертификаты 🎁»</li>
                                    <li>Нажмите «Активировать инвайт-код»</li>
                                    <li>Введите код ниже</li>
                                </ol>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="right-section">
                    <div class="code-card">
                        <div class="code-title">КОД ДЛЯ АКТИВАЦИИ</div>
                        <div class="invite-code" id="inviteCode">{invite_code}</div>
                        <button onclick="copyCode()" class="copy-button">📋 Скопировать код</button>
                        <div class="validity-info">
                            ⚠️ Код действителен до: {expiry_date}
                        </div>
                    </div>
                    
                    <div class="qr-card">
                        <div class="qr-title">БЫСТРЫЙ ПЕРЕХОД В БОТА</div>
                        <div class="qr-container">
                            <img src="{qr_code_url}" alt="QR Code для перехода в бота">
                        </div>
                        <div class="bot-reference">
                            Бот: @{bot_username}
                        </div>
                        <a href="{bot_link}" target="_blank" class="telegram-button">
                            <i class="fab fa-telegram"></i> Перейти в бота
                        </a>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <div class="actions">
                    <button onclick="printCertificate()" class="print-button">🖨️ Распечатать сертификат</button>
                </div>
                <div style="margin-top: 15px; color: #666; font-size: 11px;">
                    Сертификат №: {certificate_id}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Улучшенная функция копирования кода
        function copyCode() {{
            const code = '{invite_code}';
            const copyButton = event.target;
            const originalText = copyButton.textContent;
            
            // Пытаемся использовать современный API
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(code).then(() => {{
                    copyButton.textContent = '✅ Скопировано!';
                    copyButton.style.background = '#4CAF50';
                    copyButton.style.borderColor = '#4CAF50';
                    copyButton.style.color = 'white';
                    
                    setTimeout(() => {{
                        copyButton.textContent = originalText;
                        copyButton.style.background = '';
                        copyButton.style.borderColor = '';
                        copyButton.style.color = '';
                    }}, 2000);
                }}).catch(err => {{
                    fallbackCopy(code, copyButton, originalText);
                }});
            }} else {{
                fallbackCopy(code, copyButton, originalText);
            }}
        }}
        
        function fallbackCopy(code, button, originalText) {{
            const textArea = document.createElement('textarea');
            textArea.value = code;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {{
                const successful = document.execCommand('copy');
                if (successful) {{
                    button.textContent = '✅ Скопировано!';
                    button.style.background = '#4CAF50';
                    button.style.borderColor = '#4CAF50';
                    button.style.color = 'white';
                    
                    setTimeout(() => {{
                        button.textContent = originalText;
                        button.style.background = '';
                        button.style.borderColor = '';
                        button.style.color = '';
                    }}, 2000);
                }}
            }} catch (err) {{
                console.error('Ошибка копирования:', err);
                alert('Не удалось скопировать код. Скопируйте вручную: ' + code);
            }}
            
            document.body.removeChild(textArea);
        }}
        
        // Функция печати с улучшениями для мобильных
        function printCertificate() {{
            // На мобильных устройствах показываем подсказку
            if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {{
                if (confirm('Нажмите "ОК" для печати. На мобильном устройстве может открыться меню сохранения в PDF.')) {{
                    setupPrint();
                }}
            }} else {{
                setupPrint();
            }}
        }}
        
        function setupPrint() {{
            // Добавляем стили для печати
            const printStyles = `
                @media print {{
                    @page {{
                        size: A4;
                        margin: 0;
                    }}
                    body {{
                        margin: 0 !important;
                        padding: 0 !important;
                        background: white !important;
                        width: 210mm !important;
                        height: 297mm !important;
                    }}
                    .certificate-container {{
                        width: 210mm !important;
                        height: 297mm !important;
                        max-width: 210mm !important;
                        border: none !important;
                        margin: 0 !important;
                        border-radius: 0 !important;
                        page-break-inside: avoid;
                    }}
                    .print-button, .copy-button, .telegram-button {{
                        display: none !important;
                    }}
                    .spartan-background {{
                        opacity: 0.15 !important;
                    }}
                    .invite-code {{
                        white-space: nowrap !important;
                        overflow: visible !important;
                        text-overflow: clip !important;
                        font-size: 28px !important;
                    }}
                }}
            `;
            
            const styleEl = document.createElement('style');
            styleEl.innerHTML = printStyles;
            document.head.appendChild(styleEl);
            
            // Для мобильных делаем небольшую задержку
            setTimeout(() => {{
                window.print();
                
                // Удаляем стили после печати
                setTimeout(() => {{
                    if (styleEl.parentNode) {{
                        document.head.removeChild(styleEl);
                    }}
                }}, 100);
            }}, 100);
        }}
        
        // Автоматическая адаптация для мобильных
        document.addEventListener('DOMContentLoaded', function() {{
            // Улучшаем отображение на мобильных
            if ('ontouchstart' in window) {{
                // Добавляем класс для сенсорных устройств
                document.body.classList.add('touch-device');
                
                // Увеличиваем размеры тач-целей
                const buttons = document.querySelectorAll('button, .telegram-button');
                buttons.forEach(btn => {{
                    btn.style.minHeight = '44px';
                    btn.style.minWidth = '44px';
                }});
            }}
            
            // Адаптация инвайт-кода для мобильных
            const inviteCodeEl = document.querySelector('.invite-code');
            if (inviteCodeEl && window.innerWidth < 768) {{
                // На мобильных разбиваем длинный код
                const code = inviteCodeEl.textContent;
                if (code.length > 15) {{
                    // Добавляем мягкие переносы
                    inviteCodeEl.style.wordBreak = 'break-all';
                    inviteCodeEl.style.whiteSpace = 'normal';
                }}
            }}
            
            // Логирование открытия для отладки
            console.log('Сертификат загружен. Ширина экрана:', window.innerWidth, 'Высота:', window.innerHeight);
            console.log('User Agent:', navigator.userAgent);
        }});
        
        // Обработка изменения ориентации
        let orientationTimeout;
        window.addEventListener('orientationchange', function() {{
            clearTimeout(orientationTimeout);
            orientationTimeout = setTimeout(() => {{
                console.log('Ориентация изменена, обновляем страницу...');
                location.reload();
            }}, 300);
        }});
        
        // Обработка изменения размера окна
        let resizeTimeout;
        window.addEventListener('resize', function() {{
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {{
                console.log('Размер окна изменен:', window.innerWidth, 'x', window.innerHeight);
                
                // Адаптация кода для текущего размера
                const inviteCodeEl = document.querySelector('.invite-code');
                if (inviteCodeEl) {{
                    if (window.innerWidth < 768) {{
                        inviteCodeEl.style.wordBreak = 'break-all';
                        inviteCodeEl.style.whiteSpace = 'normal';
                    }} else {{
                        inviteCodeEl.style.wordBreak = 'keep-all';
                        inviteCodeEl.style.whiteSpace = 'nowrap';
                    }}
                }}
            }}, 200);
        }});
    </script>
</body>
</html>'''
        
        return html_content
    
    def save_certificate(self, invite_code, html_content):
        """Сохраняет сертификат в файл"""
        filename = f"spartan_certificate_{invite_code}.html"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath
    
    def generate_preview(self, filename="preview_certificate.html"):
        """Генерирует HTML файл для предпросмотра сертификата"""
        # Тестовые данные для предпросмотра
        test_invite_code = "SPARTA-GIFT-2024-ABCDEF"
        test_tariff = {
            "name": "Подарочная подписка месячная",
            "days": 30,
            "price": 300
        }
        test_buyer = {
            "first_name": "Тестовый",
            "username": "test_user",
            "user_id": 123456789
        }
        test_config = type('Config', (), {
            'BOT_USERNAME': 'pinkov300_bot',
            'SUPPORT_USERNAME': 'support_username'
        })()
        
        html_content = self.generate_certificate(
            test_invite_code, 
            test_tariff, 
            test_buyer, 
            test_config
        )
        
        preview_path = self.output_dir / filename
        with open(preview_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return preview_path

# Синглтон экземпляр
spartan_certificate_generator = SpartanCertificateGenerator()

# Функция для быстрого создания предпросмотра
def create_preview():
    """Создает файл предпросмотра и выводит путь к нему"""
    generator = SpartanCertificateGenerator()
    preview_file = generator.generate_preview()
    print(f"✅ Предпросмотр создан: {preview_file}")
    print(f"📱 Откройте файл в браузере для просмотра")
    print(f"🌐 Можно открыть через: file://{preview_file.absolute()}")
    return preview_file

if __name__ == "__main__":
    # Если запускаем файл напрямую, создаем предпросмотр
    create_preview()