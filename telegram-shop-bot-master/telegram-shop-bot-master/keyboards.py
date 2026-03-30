from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# ========== ОСНОВНЫЕ КЛАВИАТУРЫ ==========

def user_main_keyboard():
    """Клавиатура обычного пользователя"""
    keyboard = [
        [KeyboardButton("💰 Прайс-лист"), KeyboardButton("📦 Оформить заказ")],
        [KeyboardButton("📋 Мои заказы"), KeyboardButton("🤝 Приведи друга")],
        [KeyboardButton("🚪 Выход"), KeyboardButton("ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def manager_main_keyboard():
    """Клавиатура менеджера"""
    keyboard = [
        [KeyboardButton("💰 Управление прайсом"), KeyboardButton("📋 Заказы")],
        [KeyboardButton("👥 Связь с клиентами"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📢 Рассылка"), KeyboardButton("📤 Экспорт в Google Sheets")],
        [KeyboardButton("📥 Импорт товаров"), KeyboardButton("🚪 Выход")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def superadmin_main_keyboard():
    """Клавиатура суперадмина"""
    keyboard = [
        [KeyboardButton("💰 Управление прайсом"), KeyboardButton("📋 Заказы")],
        [KeyboardButton("👥 Связь с клиентами"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📢 Рассылка"), KeyboardButton("📤 Экспорт в Google Sheets")],
        [KeyboardButton("📥 Импорт товаров"), KeyboardButton("👥 Управление менеджерами")],
        [KeyboardButton("🚪 Выход")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard(user_id, db):
    """Получение клавиатуры по роли"""
    if db.is_superadmin(user_id):
        return superadmin_main_keyboard()
    else:
        return manager_main_keyboard()

# ========== ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ ==========

def cancel_keyboard():
    """Клавиатура с отменой и выходом"""
    keyboard = [["❌ Отмена"], ["🚪 Выход"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ========== INLINE КЛАВИАТУРЫ ==========

def price_menu_keyboard():
    """Меню управления прайсом"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="price_add")],
        [InlineKeyboardButton("✏️ Редактировать товар", callback_data="price_edit")],
        [InlineKeyboardButton("🗑 Удалить товар", callback_data="price_delete")],
        [InlineKeyboardButton("📊 Статус наличия", callback_data="price_toggle")],
        [InlineKeyboardButton("📤 Экспорт в Google Sheets", callback_data="price_export")],
        [InlineKeyboardButton("◀️ Назад", callback_data="price_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def orders_menu_keyboard():
    """Меню заказов"""
    keyboard = [
        [InlineKeyboardButton("📅 За сегодня", callback_data="orders_today")],
        [InlineKeyboardButton("📆 За месяц", callback_data="orders_month")],
        [InlineKeyboardButton("📅 За период", callback_data="orders_period")],
        [InlineKeyboardButton("📤 Экспорт в Google Sheets", callback_data="orders_export")],
        [InlineKeyboardButton("◀️ Назад", callback_data="orders_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def managers_menu_keyboard():
    """Меню управления менеджерами"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить менеджера", callback_data="manager_add")],
        [InlineKeyboardButton("🗑 Удалить менеджера", callback_data="manager_remove")],
        [InlineKeyboardButton("📋 Список менеджеров", callback_data="manager_list")],
        [InlineKeyboardButton("◀️ Назад", callback_data="manager_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_status_keyboard(order_id):
    """Клавиатура выбора статуса заказа"""
    from config import AVAILABLE_STATUSES
    keyboard = []
    for status_key, status_value in AVAILABLE_STATUSES.items():
        keyboard.append([InlineKeyboardButton(
            status_value, 
            callback_data=f"set_status_{order_id}_{status_key}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_orders")])
    return InlineKeyboardMarkup(keyboard)