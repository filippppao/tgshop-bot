# google_sheets.py
import logging
import gspread
import json
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID

logger = logging.getLogger(__name__)

class GoogleSheets:
    """Класс для работы с Google Sheets"""
    
    def __init__(self):
        self.client = None
        self.products_sheet = None
        self.orders_sheet = None
        self.init_google_sheets()
    
    def init_google_sheets(self):
        """Инициализация Google Sheets"""
        try:
            # Проверяем наличие файла credentials.json
            import os
            if not os.path.exists('credentials.json'):
                logger.warning("⚠️ Файл credentials.json не найден. Google Sheets отключен.")
                return
            
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
            self.client = gspread.authorize(creds)
            
            # Открываем таблицу
            spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
            
            # Создаем или получаем лист с товарами
            try:
                self.products_sheet = spreadsheet.worksheet("Товары")
            except:
                self.products_sheet = spreadsheet.add_worksheet("Товары", 1000, 20)
                headers = [["ID", "Название", "Категория", "Цена", "В наличии", "Фото ID", "Дата добавления"]]
                self.products_sheet.append_rows(headers)
            
            # Создаем или получаем лист с заказами
            try:
                self.orders_sheet = spreadsheet.worksheet("Заказы")
            except:
                self.orders_sheet = spreadsheet.add_worksheet("Заказы", 1000, 20)
                headers = [["№ заказа", "Клиент", "Username", "Телефон", "Товары", "Сумма", "Адрес", "Статус", "Дата"]]
                self.orders_sheet.append_rows(headers)
            
            logger.info("✅ Google Sheets подключен")
        except Exception as e:
            logger.error(f"❌ Ошибка Google Sheets: {e}")
    
    def export_products(self, products):
        """Экспорт товаров в Google Sheets"""
        if not self.client:
            return False, "❌ Google Sheets не подключен"
        
        try:
            # Очищаем лист кроме заголовков
            self.products_sheet.batch_clear(['A2:G1000'])
            
            # Данные
            rows = []
            for p in products:
                # p: id, name, category, price, stock, photo, created_at
                rows.append([
                    str(p[0]), str(p[1]), str(p[2]), float(p[3]), int(p[4]), 
                    str(p[5]) if p[5] else "", str(p[6]) if len(p) > 6 else ""
                ])
            
            if rows:
                self.products_sheet.append_rows(rows)
            
            logger.info(f"✅ Экспортировано {len(products)} товаров")
            return True, f"✅ Экспортировано {len(products)} товаров"
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта товаров: {e}")
            return False, f"❌ Ошибка: {str(e)[:100]}"
    
    def export_orders(self, orders):
        """Экспорт заказов в Google Sheets"""
        if not self.client:
            return False, "❌ Google Sheets не подключен"
        
        try:
            # Очищаем лист кроме заголовков
            self.orders_sheet.batch_clear(['A2:I1000'])
            
            # Данные
            rows = []
            for o in orders:
                try:
                    # o: order_id, user_name, user_phone, username, items, total, address, status, created_at
                    items = json.loads(o[4]) if o[4] else []
                    items_text = ", ".join([f"{i.get('name', '')} x{i.get('quantity', 0)}" for i in items])
                    rows.append([
                        str(o[0]), str(o[1]), str(o[3]), str(o[2]), 
                        items_text, float(o[5]), str(o[6]), str(o[7]), str(o[8][:10])
                    ])
                except:
                    continue
            
            if rows:
                self.orders_sheet.append_rows(rows)
            
            logger.info(f"✅ Экспортировано {len(rows)} заказов")
            return True, f"✅ Экспортировано {len(rows)} заказов"
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта заказов: {e}")
            return False, f"❌ Ошибка: {str(e)[:100]}"
    
    def import_products(self):
        """Импорт товаров из Google Sheets"""
        if not self.client:
            return [], ["❌ Google Sheets не подключен"]
        
        try:
            # Получаем все записи кроме заголовков
            records = self.products_sheet.get_all_values()[1:]
            
            products = []
            errors = []
            
            for i, row in enumerate(records, start=2):
                if len(row) >= 4 and row[1].strip():
                    try:
                        name = row[1].strip()
                        category = row[2].strip() if len(row) > 2 and row[2].strip() else "Общее"
                        
                        # Парсим цену
                        price_str = row[3].strip().replace(',', '.').replace(' ', '')
                        price = float(price_str) if price_str else 0
                        
                        # Парсим количество
                        stock_str = row[4].strip() if len(row) > 4 and row[4].strip() else "0"
                        stock = int(float(stock_str)) if stock_str else 0
                        
                        products.append({
                            'name': name,
                            'category': category,
                            'price': price,
                            'stock': stock
                        })
                    except Exception as e:
                        errors.append(f"Строка {i}: {str(e)}")
            
            logger.info(f"✅ Импортировано {len(products)} товаров")
            return products, errors
        except Exception as e:
            logger.error(f"❌ Ошибка импорта товаров: {e}")
            return [], [str(e)]