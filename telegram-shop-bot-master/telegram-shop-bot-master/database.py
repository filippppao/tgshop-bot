# database.py
import sqlite3
import json
import logging
import threading
import time
from datetime import datetime
from functools import lru_cache
from config import SUPER_ADMIN_IDS

logger = logging.getLogger(__name__)

class Database:
    """Оптимизированная БД с кэшированием и пулом соединений"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, db_name='shop.db'):
        if self._initialized:
            return
        self.db_name = db_name
        self.init_db()
        self.update_structure()
        self._cache = {}
        self._cache_timeout = 60  # 60 секунд кэширования
        self._initialized = True
    
    def get_connection(self):
        """Получение соединения с БД (с оптимизацией)"""
        conn = sqlite3.connect(self.db_name, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # Режим WAL для конкурентного доступа
        conn.execute("PRAGMA synchronous = NORMAL")  # Баланс скорости и надежности
        conn.execute("PRAGMA cache_size = 10000")  # Увеличиваем кэш
        return conn
    
    def _cache_get(self, key):
        """Получение из кэша"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_timeout:
                return value
        return None
    
    def _cache_set(self, key, value):
        """Сохранение в кэш"""
        self._cache[key] = (value, time.time())
    
    def _cache_clear(self, pattern=None):
        """Очистка кэша"""
        if pattern:
            self._cache = {k: v for k, v in self._cache.items() if not k.startswith(pattern)}
        else:
            self._cache.clear()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Пользователи с ролями
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                reg_date TEXT,
                last_activity TEXT,
                referrer_id INTEGER,
                referral_code TEXT UNIQUE,
                referral_count INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user',
                added_by INTEGER,
                added_date TEXT
            )
        ''')
        
        # Индексы для users
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_referral ON users(referral_code)')
        
        # Менеджеры
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS managers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                added_by INTEGER,
                added_date TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Товары
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Общее',
                price REAL NOT NULL,
                stock INTEGER DEFAULT 0,
                photo_file_id TEXT,
                in_stock INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                created_by INTEGER,
                updated_by INTEGER
            )
        ''')
        
        # Индексы для products
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_in_stock ON products(in_stock)')
        
        # Заказы с историей статусов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                user_id INTEGER,
                user_name TEXT,
                user_phone TEXT,
                username TEXT,
                items TEXT,
                total_amount REAL,
                delivery_address TEXT,
                comment TEXT,
                status TEXT DEFAULT 'new',
                status_history TEXT DEFAULT '[]',
                created_at TEXT,
                updated_at TEXT,
                processed_by INTEGER
            )
        ''')
        
        # Индексы для orders
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)')
        
        # Реферальные связи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referral_id INTEGER,
                referrer_name TEXT,
                referral_name TEXT,
                referrer_username TEXT,
                referral_username TEXT,
                registered_at TEXT,
                order_made INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        
        # Добавляем суперадминов
        for admin_id in SUPER_ADMIN_IDS:
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, role, reg_date)
                VALUES (?, ?, ?)
            ''', (admin_id, 'superadmin', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")
    
    def update_structure(self):
        """Обновление структуры БД"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Добавляем недостающие колонки
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN comment TEXT")
            logger.info("✅ Добавлена колонка comment")
        except:
            pass
        
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN status_history TEXT DEFAULT '[]'")
            logger.info("✅ Добавлена колонка status_history")
        except:
            pass
        
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN updated_at TEXT")
            logger.info("✅ Добавлена колонка updated_at")
        except:
            pass
        
        conn.commit()
        conn.close()
    
    # ========== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ==========
    
    def get_user_role(self, user_id):
        """Получение роли пользователя (с кэшированием)"""
        cache_key = f"user_role_{user_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        role = result['role'] if result else 'user'
        self._cache_set(cache_key, role)
        return role
    
    def is_superadmin(self, user_id):
        """Проверка на суперадмина"""
        return user_id in SUPER_ADMIN_IDS
    
    def is_manager(self, user_id):
        """Проверка на менеджера (с кэшированием)"""
        cache_key = f"is_manager_{user_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = ? AND role = 'manager'", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        is_manager = result is not None
        self._cache_set(cache_key, is_manager)
        return is_manager
    
    def register_user(self, user_id, username, first_name, last_name, referrer_id=None):
        """Регистрация нового пользователя"""
        import hashlib
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Генерация реферального кода
        hash_obj = hashlib.md5(f"{user_id}{datetime.now()}".encode())
        referral_code = hash_obj.hexdigest()[:10]
        
        # Определяем роль
        role = 'superadmin' if user_id in SUPER_ADMIN_IDS else 'user'
        
        cursor.execute('''
            INSERT OR IGNORE INTO users 
            (user_id, username, first_name, last_name, reg_date, last_activity, referral_code, referrer_id, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              referral_code, referrer_id, role))
        
        if referrer_id:
            # Получаем имена для реферальной записи
            cursor.execute("SELECT first_name, username FROM users WHERE user_id = ?", (referrer_id,))
            referrer = cursor.fetchone()
            
            cursor.execute('''
                INSERT INTO referrals 
                (referrer_id, referral_id, referrer_name, referral_name, referrer_username, referral_username, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                referrer_id, user_id, 
                referrer['first_name'] if referrer else None, first_name,
                referrer['username'] if referrer else None, username,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            
            cursor.execute('''
                UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?
            ''', (referrer_id,))
            
            # Очищаем кэш
            self._cache_clear(f"referrals_{referrer_id}")
        
        conn.commit()
        conn.close()
        
        # Очищаем кэш
        self._cache_clear(f"user_role_{user_id}")
        self._cache_clear(f"is_manager_{user_id}")
        
        return referral_code
    
    # ========== РАБОТА С ТОВАРАМИ ==========
    
    def get_products(self, only_in_stock=True, category=None):
        """Получение списка товаров (с кэшированием)"""
        cache_key = f"products_{only_in_stock}_{category}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT id, name, category, price, stock, photo_file_id FROM products WHERE 1=1"
        params = []
        
        if only_in_stock:
            query += " AND in_stock = 1 AND stock > 0"
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY category, name"
        
        cursor.execute(query, params)
        products = cursor.fetchall()
        conn.close()
        
        result = [dict(p) for p in products]
        self._cache_set(cache_key, result)
        return result
    
    def get_product(self, product_id):
        """Получение товара по ID (с кэшированием)"""
        cache_key = f"product_{product_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, category, price, stock, photo_file_id, in_stock
            FROM products WHERE id = ?
        ''', (product_id,))
        product = cursor.fetchone()
        conn.close()
        
        result = dict(product) if product else None
        self._cache_set(cache_key, result)
        return result
    
    def add_product(self, name, category, price, stock, photo_file_id, created_by):
        """Добавление нового товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO products 
            (name, category, price, stock, photo_file_id, in_stock, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name, category, price, stock, photo_file_id,
            1 if stock > 0 else 0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            created_by
        ))
        
        product_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Очищаем кэш товаров
        self._cache_clear("products_")
        return product_id
    
    def update_product(self, product_id, **kwargs):
        """Обновление товара"""
        allowed_fields = {'name', 'category', 'price', 'stock', 'photo_file_id', 'in_stock'}
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        values.append(product_id)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        conn.close()
        
        # Очищаем кэш
        self._cache_clear(f"product_{product_id}")
        self._cache_clear("products_")
        return True
    
    def delete_product(self, product_id):
        """Удаление товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        
        # Очищаем кэш
        self._cache_clear(f"product_{product_id}")
        self._cache_clear("products_")
        return True
    
    def toggle_stock(self, product_id):
        """Переключение статуса наличия"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT in_stock FROM products WHERE id = ?", (product_id,))
        current = cursor.fetchone()['in_stock']
        
        new_status = 0 if current else 1
        cursor.execute('''
            UPDATE products SET in_stock = ?, updated_at = ? WHERE id = ?
        ''', (new_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), product_id))
        
        conn.commit()
        conn.close()
        
        # Очищаем кэш
        self._cache_clear(f"product_{product_id}")
        self._cache_clear("products_")
        return new_status
    
    # ========== РАБОТА С ЗАКАЗАМИ ==========
    
    def create_order(self, user_id, user_name, user_phone, username, items, total, address, comment):
        """Создание нового заказа"""
        import random
        import string
        
        # Генерация номера заказа
        date = datetime.now().strftime("%Y%m%d")
        random_part = ''.join(random.choices(string.digits, k=6))
        order_id = f"ORD-{date}-{random_part}"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # История статусов
        history = [{
            'from': 'none',
            'to': 'new',
            'changed_by': user_id,
            'changed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }]
        
        cursor.execute('''
            INSERT INTO orders 
            (order_id, user_id, user_name, user_phone, username, items, total_amount, 
             delivery_address, comment, status, status_history, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_id, user_id, user_name, user_phone, username,
            json.dumps(items, ensure_ascii=False), total, address, comment,
            'new', json.dumps(history, ensure_ascii=False),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        
        # Обновляем остатки товаров
        for item in items:
            cursor.execute('''
                UPDATE products 
                SET stock = stock - ?, 
                    in_stock = CASE WHEN (stock - ?) > 0 THEN 1 ELSE 0 END
                WHERE id = ?
            ''', (item['quantity'], item['quantity'], item['product_id']))
            
            # Очищаем кэш товара
            self._cache_clear(f"product_{item['product_id']}")
        
        # Если есть реферальная связь, обновляем
        cursor.execute('''
            SELECT r.id, r.referrer_id 
            FROM referrals r
            WHERE r.referral_id = ? AND r.order_made = 0
        ''', (user_id,))
        
        referral = cursor.fetchone()
        if referral:
            cursor.execute('UPDATE referrals SET order_made = 1 WHERE id = ?', (referral['id'],))
            
            # Увеличиваем счетчик рефералов
            cursor.execute('''
                UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?
            ''', (referral['referrer_id'],))
            
            # Очищаем кэш
            self._cache_clear(f"user_role_{referral['referrer_id']}")
        
        conn.commit()
        conn.close()
        
        # Очищаем кэш заказов
        self._cache_clear("orders_")
        self._cache_clear("products_")
        
        return order_id
    
    def get_orders(self, period='all', user_id=None, limit=50):
        """Получение заказов (с кэшированием)"""
        cache_key = f"orders_{period}_{user_id}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM orders WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if period == 'today':
            query += " AND date(created_at) = date('now', 'localtime')"
        elif period == 'month':
            query += " AND created_at >= datetime('now', '-30 days')"
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        orders = cursor.fetchall()
        conn.close()
        
        result = [dict(o) for o in orders]
        self._cache_set(cache_key, result)
        return result
    
    def get_order(self, order_id):
        """Получение заказа по ID (с кэшированием)"""
        cache_key = f"order_{order_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        result = dict(order) if order else None
        self._cache_set(cache_key, result)
        return result
    
    def update_order_status(self, order_id, new_status, admin_id):
        """Обновление статуса заказа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT status, status_history, user_id FROM orders WHERE order_id = ?", (order_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False, "Заказ не найден"
        
        current_status, history_json, user_id = result
        
        try:
            history = json.loads(history_json) if history_json else []
        except:
            history = []
        
        history.append({
            'from': current_status,
            'to': new_status,
            'changed_by': admin_id,
            'changed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        cursor.execute('''
            UPDATE orders 
            SET status = ?, status_history = ?, updated_at = ?, processed_by = ?
            WHERE order_id = ?
        ''', (new_status, json.dumps(history, ensure_ascii=False), 
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, order_id))
        
        conn.commit()
        conn.close()
        
        # Очищаем кэш
        self._cache_clear(f"order_{order_id}")
        self._cache_clear("orders_")
        
        return True, {'user_id': user_id, 'new_status': new_status}
    
    # ========== УПРАВЛЕНИЕ МЕНЕДЖЕРАМИ ==========
    
    def add_manager(self, manager_id, added_by):
        """Добавление менеджера"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET role = 'manager', added_by = ?, added_date = ?
            WHERE user_id = ?
        ''', (added_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), manager_id))
        
        cursor.execute('''
            INSERT OR REPLACE INTO managers (user_id, added_by, added_date, is_active)
            VALUES (?, ?, ?, 1)
        ''', (manager_id, added_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        # Очищаем кэш
        self._cache_clear(f"user_role_{manager_id}")
        self._cache_clear("managers_")
        
        return True
    
    def remove_manager(self, manager_id):
        """Удаление менеджера"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET role = 'user' WHERE user_id = ?", (manager_id,))
        cursor.execute("UPDATE managers SET is_active = 0 WHERE user_id = ?", (manager_id,))
        
        conn.commit()
        conn.close()
        
        # Очищаем кэш
        self._cache_clear(f"user_role_{manager_id}")
        self._cache_clear("managers_")
        
        return True
    
    def get_managers(self, active_only=True):
        """Получение списка менеджеров (с кэшированием)"""
        cache_key = f"managers_{active_only}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT u.user_id, u.first_name, u.username, u.added_date, m.added_by
            FROM users u
            JOIN managers m ON u.user_id = m.user_id
            WHERE u.role = 'manager'
        '''
        if active_only:
            query += " AND m.is_active = 1"
        
        cursor.execute(query)
        managers = cursor.fetchall()
        conn.close()
        
        result = [dict(m) for m in managers]
        self._cache_set(cache_key, result)
        return result
    
    # ========== РЕФЕРАЛЫ ==========
    
    def get_referrals(self, user_id):
        """Получение списка рефералов пользователя (с кэшированием)"""
        cache_key = f"referrals_{user_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT referral_name, referral_username, order_made, registered_at
            FROM referrals
            WHERE referrer_id = ?
            ORDER BY registered_at DESC
        ''', (user_id,))
        referrals = cursor.fetchall()
        conn.close()
        
        result = [dict(r) for r in referrals]
        self._cache_set(cache_key, result)
        return result
    
    # ========== СТАТИСТИКА ==========
    
    def get_stats(self):
    
        """Получение статистики (с кэшированием)"""
        cache_key = "stats"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Товары
        cursor.execute("SELECT COUNT(*) FROM products")
        stats['total_products'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE in_stock = 1 AND stock > 0")
        stats['in_stock'] = cursor.fetchone()[0]
        
        # ВАЖНО: Добавляем вычисление общего количества товаров на складе
        cursor.execute("SELECT SUM(stock) FROM products")
        total_stock = cursor.fetchone()[0]
        stats['total_stock'] = total_stock if total_stock else 0
        
        # Пользователи
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
        stats['total_users'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'manager'")
        stats['total_managers'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL")
        stats['referred_users'] = cursor.fetchone()[0]
        
        # Заказы
        cursor.execute("SELECT COUNT(*) FROM orders")
        stats['total_orders'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(total_amount) FROM orders")
        total_revenue = cursor.fetchone()[0]
        stats['total_revenue'] = total_revenue if total_revenue else 0
        
        cursor.execute("SELECT AVG(total_amount) FROM orders")
        avg_order = cursor.fetchone()[0]
        stats['avg_order'] = avg_order if avg_order else 0
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE date(created_at) = date('now', 'localtime')")
        stats['orders_today'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(total_amount) FROM orders WHERE date(created_at) = date('now', 'localtime')")
        revenue_today = cursor.fetchone()[0]
        stats['revenue_today'] = revenue_today if revenue_today else 0
        
        # Рефералы
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE order_made = 1")
        stats['referrals_with_orders'] = cursor.fetchone()[0]
        
        # Топ рефереров
        cursor.execute('''
            SELECT u.first_name, u.username, COUNT(r.id) as ref_count, SUM(r.order_made) as orders_made
            FROM users u
            JOIN referrals r ON u.user_id = r.referrer_id
            GROUP BY u.user_id
            ORDER BY ref_count DESC
            LIMIT 5
        ''')
        stats['top_referrers'] = [dict(t) for t in cursor.fetchall()]
        
        conn.close()
        
        self._cache_set(cache_key, stats)
        return stats