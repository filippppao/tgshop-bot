# handlers/user.py
import logging
import json
import asyncio
from handlers.common import exit_handler
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from database import Database
from keyboards import *
from states import *
from utils.validators import validate_phone
from utils.formatters import escape_markdown, format_number
from config import ORDER_STATUSES
from handlers.common import exit_handler

logger = logging.getLogger(__name__)
db = Database()

# ========== СТАРТ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    user = update.effective_user
    
    logger.info(f"👤 Пользователь {user.id} ({user.first_name}) запустил бота")
    
    # Проверка реферальной ссылки
    args = context.args
    referrer_id = None
    if args and len(args) > 0:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (args[0],))
        result = cursor.fetchone()
        if result and result['user_id'] != user.id:
            referrer_id = result['user_id']
            logger.info(f"👤 Пользователь {user.id} перешел по реферальной ссылке от {referrer_id}")
        conn.close()
    
    # Регистрация пользователя
    db.register_user(user.id, user.username, user.first_name, user.last_name, referrer_id)
    
    context.user_data.clear()
    
    if db.is_superadmin(user.id):
        await update.message.reply_text(
            f"👑 *СУПЕРАДМИНИСТРАТОР*\n\n"
            f"Здравствуйте, {escape_markdown(user.first_name)}!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=superadmin_main_keyboard()
        )
        return SUPERADMIN
    elif db.is_manager(user.id):
        await update.message.reply_text(
            f"👔 *МЕНЕДЖЕР*\n\n"
            f"Здравствуйте, {escape_markdown(user.first_name)}!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=manager_main_keyboard()
        )
        return ADMIN
    else:
        await update.message.reply_text(
            f"👋 Привет, {escape_markdown(user.first_name)}! Добро пожаловать в магазин!",
            reply_markup=user_main_keyboard()
        )
        return MAIN

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========

async def user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для обычных пользователей"""
    text = update.message.text
    user_id = update.effective_user.id
    
    logger.info(f"👤 Пользователь {user_id}: {text}")
    
    if text == "💰 Прайс-лист":
        return await show_price_list(update, context)
    elif text == "📦 Оформить заказ":
        return await start_order(update, context)
    elif text == "📋 Мои заказы":
        return await show_my_orders(update, context)
    elif text == "🤝 Приведи друга":
        return await show_referral(update, context)
    elif text == "ℹ️ Помощь":
        return await show_help(update, context)
    elif text == "🚪 Выход":
        return await exit_handler(update, context)
    
    return MAIN

# ========== ПРАЙС-ЛИСТ ==========

async def show_price_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ прайс-листа"""
    user_id = update.effective_user.id
    logger.info(f"👤 Пользователь {user_id}: просмотр прайс-листа")
    
    products = db.get_products(only_in_stock=True)
    
    if not products:
        await update.message.reply_text("😕 Товаров в наличии нет")
        return MAIN
    
    # Группируем по категориям
    categories = {}
    for p in products:
        if p['category'] not in categories:
            categories[p['category']] = []
        categories[p['category']].append(p)
    
    for category, items in categories.items():
        await update.message.reply_text(
            f"📂 *{escape_markdown(category)}*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        for item in items:
            text = (
                f"📦 *{escape_markdown(item['name'])}*\n"
                f"💰 Цена: {format_number(item['price'])}₽\n"
                f"📊 В наличии: {item['stock']} шт.\n"
                f"🆔 ID: `{item['id']}`"
            )
            
            if item['photo_file_id']:
                try:
                    await update.message.reply_photo(
                        photo=item['photo_file_id'],
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            
            await asyncio.sleep(0.3)
    
    return MAIN

# ========== ПОМОЩЬ ==========

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ помощи с контактами менеджера"""
    user_id = update.effective_user.id
    logger.info(f"👤 Пользователь {user_id}: открыл помощь")
    
    # Получаем контакт менеджера (первого активного)
    manager_contact = "не назначен"
    manager_name = "Менеджер"
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT first_name, username FROM users 
            WHERE role = 'manager' AND username IS NOT NULL 
            LIMIT 1
        ''')
        manager = cursor.fetchone()
        conn.close()
        
        if manager:
            if manager['username']:
                manager_contact = f"@{manager['username']}"
            elif manager['first_name']:
                manager_contact = manager['first_name']
            manager_name = manager['first_name'] or "Менеджер"
    except Exception as e:
        logger.error(f"Ошибка получения контакта менеджера: {e}")
    
    # Текст БЕЗ Markdown разметки (простой текст)
    text = (
        "🔹 ПОМОЩЬ ПО ИСПОЛЬЗОВАНИЮ БОТА 🔹\n\n"
        "ОСНОВНЫЕ КОМАНДЫ:\n"
        "💰 Прайс-лист - просмотр всех доступных товаров\n"
        "📦 Оформить заказ - создание нового заказа\n"
        "📋 Мои заказы - история ваших заказов\n"
        "🤝 Приведи друга - реферальная программа\n"
        "🚪 Выход - вернуться в главное меню\n\n"
        
        "КАК СДЕЛАТЬ ЗАКАЗ:\n"
        "1. Нажмите '📦 Оформить заказ'\n"
        "2. Введите ваше ФИО\n"
        "3. Введите номер телефона (например: +7 999 123-45-67)\n"
        "4. Выберите товар по ID из прайс-листа\n"
        "5. Укажите количество\n"
        "6. Введите адрес доставки\n"
        "7. Добавьте комментарий (или отправьте '-')\n"
        "8. Подтвердите заказ\n\n"
        
        "РЕФЕРАЛЬНАЯ ПРОГРАММА:\n"
        "• Приглашайте друзей по уникальной ссылке\n"
        "• Когда друг сделает первый заказ - вы получите бонус\n"
        "• Размер бонуса уточняйте у менеджера\n\n"
        
        f"СВЯЗЬ С МЕНЕДЖЕРОМ: {manager_contact}\n\n @filimillance"
        
        "ЕСЛИ ВОЗНИКЛИ ПРОБЛЕМЫ:\n"
        "• Проверьте правильность введенных данных\n"
        "• Убедитесь, что товар есть в наличии\n"
        f"• Напишите {manager_name} - поможем!"
    )
    
    # Отправляем БЕЗ parse_mode (обычный текст)
    await update.message.reply_text(text)
    return MAIN

# ========== ОФОРМЛЕНИЕ ЗАКАЗА ==========

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало оформления заказа"""
    user_id = update.effective_user.id
    logger.info(f"👤 Пользователь {user_id}: начал оформление заказа")
    
    context.user_data['order'] = {}
    await update.message.reply_text(
        "📝 *ОФОРМЛЕНИЕ ЗАКАЗА*\n\n"
        "Шаг 1/6: Введите ваше ФИО:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_keyboard()
    )
    return ORDER_FIO

async def order_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ФИО"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text in ["❌ Отмена", "🚪 Выход"]:
        logger.info(f"👤 Пользователь {user_id}: отменил заказ")
        return await exit_handler(update, context)
    
    context.user_data['order']['fio'] = text
    logger.info(f"👤 Пользователь {user_id}: ввел ФИО")
    
    await update.message.reply_text(
        "📞 Шаг 2/6: Введите номер телефона (например: +7 999 123-45-67):",
        reply_markup=cancel_keyboard()
    )
    return ORDER_PHONE

async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение телефона"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text in ["❌ Отмена", "🚪 Выход"]:
        logger.info(f"👤 Пользователь {user_id}: отменил заказ")
        return await exit_handler(update, context)
    
    is_valid, phone = validate_phone(text)
    if not is_valid:
        logger.warning(f"👤 Пользователь {user_id}: неверный формат телефона: {text}")
        examples = (
            "❌ *Ошибка*\n\n"
            f"{phone}\n\n"
            "✅ *Примеры правильного ввода:*\n"
            "• +7 999 123-45-67\n"
            "• 89991234567\n"
            "• 79991234567"
        )
        await update.message.reply_text(examples, parse_mode=ParseMode.MARKDOWN)
        return ORDER_PHONE
    
    context.user_data['order']['phone'] = phone
    logger.info(f"👤 Пользователь {user_id}: ввел телефон {phone}")
    
    products = db.get_products(only_in_stock=True)
    if not products:
        await update.message.reply_text("😕 Товаров нет", reply_markup=user_main_keyboard())
        return MAIN
    
    text = "🛒 Шаг 3/6: Введите ID товара:\n\n"
    for p in products[:10]:
        text += f"ID {p['id']}: *{escape_markdown(p['name'])}* - {p['price']}₽\n"
    
    context.user_data['available_products'] = products
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_keyboard())
    return ORDER_PRODUCT

async def order_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор товара"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text in ["❌ Отмена", "🚪 Выход"]:
        logger.info(f"👤 Пользователь {user_id}: отменил заказ")
        return await exit_handler(update, context)
    
    try:
        product_id = int(text)
        products = context.user_data.get('available_products', [])
        selected = None
        for p in products:
            if p['id'] == product_id:
                selected = p
                break
        
        if not selected:
            logger.warning(f"👤 Пользователь {user_id}: ввел несуществующий ID товара {product_id}")
            await update.message.reply_text("❌ Товар не найден")
            return ORDER_PRODUCT
        
        context.user_data['order']['product_id'] = product_id
        context.user_data['order']['product_name'] = selected['name']
        context.user_data['order']['product_price'] = selected['price']
        context.user_data['order']['max_stock'] = selected['stock']
        
        logger.info(f"👤 Пользователь {user_id}: выбрал товар {selected['name']} (ID: {product_id})")
        
        await update.message.reply_text(
            f"🔢 Шаг 4/6: Введите количество (до {selected['stock']} шт.):",
            reply_markup=cancel_keyboard()
        )
        return ORDER_QUANTITY
        
    except ValueError:
        logger.warning(f"👤 Пользователь {user_id}: ввел не число в ID товара: {text}")
        await update.message.reply_text("❌ Введите число")
        return ORDER_PRODUCT

async def order_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение количества"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text in ["❌ Отмена", "🚪 Выход"]:
        logger.info(f"👤 Пользователь {user_id}: отменил заказ")
        return await exit_handler(update, context)
    
    try:
        qty = int(text)
        max_stock = context.user_data['order']['max_stock']
        
        if qty <= 0 or qty > max_stock:
            logger.warning(f"👤 Пользователь {user_id}: ввел неверное количество {qty} (макс: {max_stock})")
            await update.message.reply_text(f"❌ Введите число от 1 до {max_stock}")
            return ORDER_QUANTITY
        
        context.user_data['order']['quantity'] = qty
        logger.info(f"👤 Пользователь {user_id}: выбрал количество {qty}")
        
        await update.message.reply_text(
            "📍 Шаг 5/6: Введите адрес доставки:",
            reply_markup=cancel_keyboard()
        )
        return ORDER_ADDRESS
        
    except ValueError:
        logger.warning(f"👤 Пользователь {user_id}: ввел не число в количестве: {text}")
        await update.message.reply_text("❌ Введите число")
        return ORDER_QUANTITY

async def order_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение адреса"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text in ["❌ Отмена", "🚪 Выход"]:
        logger.info(f"👤 Пользователь {user_id}: отменил заказ")
        return await exit_handler(update, context)
    
    context.user_data['order']['address'] = text
    logger.info(f"👤 Пользователь {user_id}: ввел адрес")
    
    await update.message.reply_text(
        "💬 Шаг 6/6: Комментарий к заказу (или отправьте '-' если нет комментария):",
        reply_markup=cancel_keyboard()
    )
    return ORDER_COMMENT

async def order_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение комментария"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text in ["❌ Отмена", "🚪 Выход"]:
        logger.info(f"👤 Пользователь {user_id}: отменил заказ")
        return await exit_handler(update, context)
    
    order = context.user_data['order']
    order['comment'] = "" if text == "-" else text
    
    total = order['product_price'] * order['quantity']
    
    confirm_text = (
        "📋 *ПРОВЕРЬТЕ ЗАКАЗ*\n\n"
        f"👤 ФИО: {escape_markdown(order['fio'])}\n"
        f"📞 Телефон: {order['phone']}\n"
        f"🛒 Товар: {escape_markdown(order['product_name'])}\n"
        f"🔢 Количество: {order['quantity']}\n"
        f"💰 Сумма: {format_number(total)}₽\n"
        f"📍 Адрес: {escape_markdown(order['address'])}\n"
        f"💬 Комментарий: {escape_markdown(order['comment']) or '—'}\n\n"
        "✅ Подтверждаете заказ?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data="confirm_order")],
        [InlineKeyboardButton("❌ Нет", callback_data="cancel_order")]
    ]
    
    await update.message.reply_text(
        confirm_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ORDER_CONFIRM

async def confirm_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение заказа"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "cancel_order":
        logger.info(f"👤 Пользователь {user_id}: отменил заказ")
        await query.edit_message_text("❌ Заказ отменен")
        await query.message.reply_text("Главное меню", reply_markup=user_main_keyboard())
        context.user_data.clear()
        return MAIN
    
    order = context.user_data.get('order', {})
    if not order:
        logger.error(f"❌ Ошибка: данные заказа не найдены для пользователя {user_id}")
        await query.edit_message_text("❌ Ошибка")
        return MAIN
    
    user = update.effective_user
    items = [{
        'product_id': order['product_id'],
        'name': order['product_name'],
        'price': order['product_price'],
        'quantity': order['quantity']
    }]
    total = order['product_price'] * order['quantity']
    
    # Создаем заказ в БД
    order_id = db.create_order(
        user.id, order['fio'], order['phone'], user.username,
        items, total, order['address'], order.get('comment', '')
    )
    
    logger.info(f"✅ Пользователь {user_id} оформил заказ №{order_id}")
    
    await query.edit_message_text(
        f"✅ *ЗАКАЗ №{order_id} ПОДТВЕРЖДЕН!*\n\n"
        f"Спасибо за покупку!\n"
        f"Менеджер свяжется с вами в ближайшее время.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Уведомление админам
    await notify_admins(update, context, order_id, order, user, total)
    
    await query.message.reply_text("Главное меню", reply_markup=user_main_keyboard())
    context.user_data.clear()
    return MAIN

# ========== МОИ ЗАКАЗЫ ==========

async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ заказов пользователя"""
    user_id = update.effective_user.id
    logger.info(f"👤 Пользователь {user_id}: просмотр своих заказов")
    
    orders = db.get_orders(user_id=user_id)
    
    if not orders:
        await update.message.reply_text("📭 У вас пока нет заказов")
        return MAIN
    
    text = "📋 *МОИ ЗАКАЗЫ*\n\n"
    for o in orders[:5]:
        items = json.loads(o['items'])
        items_text = ", ".join([f"{i['name']} x{i['quantity']}" for i in items])
        status = ORDER_STATUSES.get(o['status'], o['status'])
        
        text += f"🔹 *Заказ №{o['order_id']}*\n"
        text += f"📅 {o['created_at'][:10]}\n"
        text += f"🛒 {items_text}\n"
        text += f"💰 {format_number(o['total_amount'])}₽\n"
        text += f"📊 Статус: {status}\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return MAIN

# ========== РЕФЕРАЛЬНАЯ ПРОГРАММА ==========

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ реферальной программы"""
    user_id = update.effective_user.id
    logger.info(f"👤 Пользователь {user_id}: открыл реферальную программу")
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT referral_code, referral_count FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    cursor.execute('''
        SELECT referral_name, referral_username, order_made, registered_at
        FROM referrals
        WHERE referrer_id = ?
        ORDER BY registered_at DESC
    ''', (user_id,))
    referrals = cursor.fetchall()
    
    conn.close()
    
    if not user_data:
        await update.message.reply_text("❌ Ошибка получения данных")
        return MAIN
    
    referral_code = user_data['referral_code']
    count = user_data['referral_count'] or 0
    
    bot = await context.bot.get_me()
    link = f"https://t.me/{bot.username}?start={referral_code}"
    
    text = (
        "🤝 *РЕФЕРАЛЬНАЯ ПРОГРАММА*\n\n"
        f"🔗 *Ваша уникальная ссылка:*\n"
        f"`{link}`\n\n"
        f"📊 *Ваша статистика:*\n"
        f"• Приглашено друзей: {count}\n\n"
        f"🎁 *Как это работает:*\n"
        f"1️⃣ Отправьте свою ссылку другу\n"
        f"2️⃣ Друг переходит и регистрируется в боте\n"
        f"3️⃣ Когда друг сделает первый заказ, вы получите **бонус**\n"
        f"4️⃣ Размер бонуса уточняйте у менеджера\n\n"
    )
    
    if referrals:
        text += "👥 *Приглашенные друзья:*\n"
        for ref in referrals[:5]:
            name = ref['referral_name'] or ref['referral_username'] or "Пользователь"
            username = f" (@{ref['referral_username']})" if ref['referral_username'] else ""
            status = "✅ Сделал заказ" if ref['order_made'] else "⏳ Ожидает заказ"
            date = ref['registered_at'][:10] if ref['registered_at'] else ""
            text += f"• {escape_markdown(name)}{username} — {status} ({date})\n"
    else:
        text += "👥 У вас пока нет приглашенных друзей"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return MAIN

# ========== УВЕДОМЛЕНИЯ ==========

async def notify_admins(update, context, order_id, order, user, total):
    """Уведомление админов о новом заказе"""
    username = f" (@{user.username})" if user.username else ""
    msg = (
        f"🆕 *НОВЫЙ ЗАКАЗ!*\n\n"
        f"📦 №: {order_id}\n"
        f"👤 Клиент: {escape_markdown(order['fio'])}{escape_markdown(username)}\n"
        f"📞 Телефон: {order['phone']}\n"
        f"🛒 Товар: {escape_markdown(order['product_name'])} x{order['quantity']}\n"
        f"💰 Сумма: {format_number(total)}₽\n"
        f"📍 Адрес: {escape_markdown(order['address'])}\n"
        f"💬 Комментарий: {escape_markdown(order.get('comment', '')) or '—'}"
    )
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE role IN ('superadmin', 'manager')")
    admins = cursor.fetchall()
    conn.close()
    
    for admin in admins:
        try:
            await context.bot.send_message(admin['user_id'], msg, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"✅ Уведомление отправлено админу {admin['user_id']}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление админу {admin['user_id']}: {e}")