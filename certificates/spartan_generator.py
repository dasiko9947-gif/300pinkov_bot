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
        """Генерирует спартанский сертификат формата А4"""
        expiry_date = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
        
        # Форматируем названия
        tariff_description = self.format_tariff_description(tariff_data)
        
        bot_username = getattr(config, 'BOT_USERNAME', 'ваш_бот_username')
        certificate_id = f"CERT-{invite_code[:8].upper()}"
        
        # QR-код для перехода в бота
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://t.me/{bot_username}"
        
        # Получаем изображение спартанца
        spartan_image_base64 = self.get_spartan_image_base64()
        
        html_content = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Подарочный сертификат «300 ПИНКОВ»</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Roboto:wght@300;400;500&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Roboto', sans-serif;
            background: #000;
            color: #fff;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 10mm;
        }}
        
        /* Формат А4 */
        .certificate-container {{
            width: 210mm;
            height: 297mm;
            position: relative;
            background: #0a0a0a;
            border: 3px solid #d40000;
            overflow: hidden;
        }}
        
        /* Фоновое изображение спартанца */
        .spartan-background {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0.25;
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            z-index: 1;
        }}
        
        .certificate-content {{
            position: relative;
            z-index: 2;
            height: 100%;
            padding: 15mm;
            display: flex;
            flex-direction: column;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 8mm;
        }}
        
        .main-title {{
            font-family: 'Cinzel', serif;
            font-size: 48px;
            font-weight: 900;
            color: #ff3333;
            text-transform: uppercase;
            letter-spacing: 4px;
            margin-bottom: 5px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8);
        }}
        
        .subtitle {{
            font-family: 'Cinzel', serif;
            font-size: 22px;
            color: #ff6666;
            letter-spacing: 2px;
        }}
        
        .bot-description {{
            text-align: center;
            margin-bottom: 8mm;
            padding: 5mm;
            background: rgba(212, 0, 0, 0.1);
            border-radius: 3mm;
            border-left: 4px solid #d40000;
        }}
        
        .bot-description p {{
            color: #e0e0e0;
            font-size: 16px;
            line-height: 1.5;
            margin-bottom: 3mm;
        }}
        
        .content-wrapper {{
            display: flex;
            flex: 1;
            gap: 12mm;
            margin-bottom: 8mm;
        }}
        
        .left-section {{
            flex: 3;
            display: flex;
            flex-direction: column;
            gap: 8mm;
        }}
        
        .right-section {{
            flex: 2;
            display: flex;
            flex-direction: column;
            gap: 8mm;
        }}
        
        .gift-card {{
            background: rgba(212, 0, 0, 0.15);
            border: 2px solid rgba(212, 0, 0, 0.5);
            padding: 6mm;
            border-radius: 4mm;
        }}
        
        .gift-card h3 {{
            font-family: 'Cinzel', serif;
            color: #ff3333;
            font-size: 22px;
            margin-bottom: 4mm;
            text-align: center;
        }}
        
        .subscription-type {{
            background: rgba(212, 0, 0, 0.25);
            padding: 4mm;
            border-radius: 3mm;
            margin: 4mm 0;
            text-align: center;
            font-size: 18px;
            font-weight: 500;
            color: #fff;
        }}
        
        .detail-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 3mm;
            margin-top: 4mm;
        }}
        
        .detail-item {{
            background: rgba(0, 0, 0, 0.4);
            padding: 3mm;
            border-radius: 2mm;
            border: 1px solid rgba(212, 0, 0, 0.3);
            text-align: center;
        }}
        
        .detail-label {{
            color: #ff9999;
            font-size: 12px;
            margin-bottom: 1mm;
        }}
        
        .detail-value {{
            color: #fff;
            font-weight: 500;
            font-size: 16px;
        }}
        
        .code-card {{
            background: rgba(0, 0, 0, 0.5);
            border: 3px solid #d40000;
            padding: 6mm;
            border-radius: 4mm;
            text-align: center;
        }}
        
        .code-title {{
            color: #ff6666;
            font-size: 18px;
            margin-bottom: 4mm;
            text-transform: uppercase;
        }}
        
        .invite-code {{
            font-family: 'Courier New', monospace;
            font-size: 32px;
            font-weight: bold;
            color: #fff;
            background: rgba(0, 0, 0, 0.6);
            padding: 4mm;
            border-radius: 3mm;
            margin: 4mm 0;
            border: 2px solid rgba(212, 0, 0, 0.5);
            letter-spacing: 3px;
            word-break: keep-all;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .copy-button {{
            background: transparent;
            color: #ff3333;
            border: 2px solid #ff3333;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 3mm;
            transition: all 0.3s;
            font-size: 14px;
        }}
        
        .copy-button:hover {{
            background: #ff3333;
            color: #000;
        }}
        
        .validity-info {{
            color: #ff9999;
            font-size: 14px;
            margin-top: 3mm;
        }}
        
        .instructions {{
            background: rgba(255, 255, 255, 0.05);
            padding: 5mm;
            border-radius: 3mm;
            margin-top: 4mm;
            border: 1px solid rgba(212, 0, 0, 0.3);
        }}
        
        .instructions h4 {{
            color: #ff3333;
            font-size: 16px;
            margin-bottom: 3mm;
            text-align: center;
        }}
        
        .instruction-steps {{
            color: #cccccc;
            font-size: 14px;
            line-height: 1.6;
        }}
        
        .instruction-steps ol {{
            padding-left: 20px;
            margin: 2mm 0;
        }}
        
        .instruction-steps li {{
            margin-bottom: 2mm;
        }}
        
        .qr-card {{
            background: rgba(255, 255, 255, 0.05);
            padding: 6mm;
            border-radius: 4mm;
            text-align: center;
        }}
        
        .qr-title {{
            color: #ff6666;
            font-size: 16px;
            margin-bottom: 3mm;
        }}
        
        .qr-container {{
            margin: 3mm auto;
            width: 140px;
            height: 140px;
            background: white;
            padding: 2mm;
            border-radius: 2mm;
        }}
        
        .qr-container img {{
            width: 100%;
            height: 100%;
        }}
        
        .bot-reference {{
            color: #cccccc;
            font-size: 14px;
            margin-top: 3mm;
        }}
        
        .footer {{
            text-align: center;
            padding-top: 5mm;
            border-top: 1px solid rgba(212, 0, 0, 0.3);
            color: #999;
            font-size: 12px;
        }}
        
        .actions {{
            margin-top: 5mm;
            display: flex;
            justify-content: center;
            gap: 10mm;
        }}
        
        .print-button {{
            background: linear-gradient(135deg, #d40000, #ff3333);
            color: white;
            padding: 10px 25px;
            border-radius: 25px;
            border: none;
            font-weight: bold;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
        }}
        
        .print-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(212, 0, 0, 0.4);
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
            }}
            
            .certificate-container {{
                width: 210mm !important;
                height: 297mm !important;
                border: none !important;
                margin: 0 !important;
                page-break-inside: avoid;
            }}
            
            .certificate-content {{
                padding: 15mm !important;
            }}
            
            .print-button, .copy-button {{
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
            }}
        }}
        
        /* Мобильная адаптация */
        @media (max-width: 768px) {{
            body {{
                padding: 5mm;
            }}
            
            .certificate-container {{
                transform: scale(0.95);
                transform-origin: top center;
            }}
            
            .content-wrapper {{
                flex-direction: column;
                gap: 8mm;
            }}
            
            .invite-code {{
                font-size: 28px;
                padding: 3mm;
                white-space: normal;
                word-break: break-all;
            }}
            
            .qr-container {{
                width: 120px;
                height: 120px;
            }}
            
            .actions {{
                flex-direction: column;
                gap: 3mm;
            }}
        }}
    </style>
</head>
<body>
    <div class="certificate-container">
        <!-- Фоновое изображение спартанца -->
        <div class="spartan-background" style="background-image: url('data:image/jpeg;base64,{spartan_image_base64 if spartan_image_base64 else ''}')"></div>
        
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
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <div class="actions">
                    <button onclick="printCertificate()" class="print-button">🖨️ Распечатать сертификат (А4)</button>
                </div>
                <div style="margin-top: 4mm; color: #666; font-size: 11px;">
                    Сертификат №: {certificate_id}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function copyCode() {{
            const code = '{invite_code}';
            const tempInput = document.createElement('textarea');
            tempInput.value = code;
            document.body.appendChild(tempInput);
            tempInput.select();
            tempInput.setSelectionRange(0, 99999);
            
            try {{
                const successful = document.execCommand('copy');
                if (successful) {{
                    alert('✅ Код скопирован: ' + code);
                }} else {{
                    alert('❌ Не удалось скопировать код. Скопируйте вручную: ' + code);
                }}
            }} catch (err) {{
                // Пробуем использовать современный API
                navigator.clipboard.writeText(code).then(() => {{
                    alert('✅ Код скопирован: ' + code);
                }}).catch(() => {{
                    alert('❌ Ошибка копирования. Скопируйте вручную: ' + code);
                }});
            }}
            
            document.body.removeChild(tempInput);
        }}
        
        function printCertificate() {{
            // Сохраняем оригинальные стили
            const originalStyles = document.querySelector('style').innerHTML;
            
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
                        -webkit-print-color-adjust: exact !important;
                        print-color-adjust: exact !important;
                    }}
                    .certificate-container {{
                        width: 210mm !important;
                        height: 297mm !important;
                        border: none !important;
                        margin: 0 !important;
                        page-break-inside: avoid;
                    }}
                    .print-button, .copy-button {{
                        display: none !important;
                    }}
                    .spartan-background {{
                        opacity: 0.15 !important;
                    }}
                    .invite-code {{
                        white-space: nowrap !important;
                        overflow: visible !important;
                        text-overflow: clip !important;
                    }}
                }}
            `;
            
            // Создаем элемент со стилями для печати
            const styleEl = document.createElement('style');
            styleEl.innerHTML = printStyles;
            document.head.appendChild(styleEl);
            
            // Печатаем
            window.print();
            
            // Удаляем добавленные стили
            setTimeout(() => {{
                document.head.removeChild(styleEl);
            }}, 100);
        }}
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

# Синглтон экземпляр
spartan_certificate_generator = SpartanCertificateGenerator()