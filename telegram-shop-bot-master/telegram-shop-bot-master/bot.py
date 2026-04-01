#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Shop Bot - Оптимизированная версия для 100+ пользователей
"""

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
import os

# Конфигурация
from config import BOT_TOKEN

# База данных
from database import Database

# Состояния
from states import *

# Клавиатуры
from keyboards import get_admin_keyboard, user_main_keyboard, manager_main_keyboard, superadmin_main_keyboard

# Обработчики пользователя
from handlers.user import (
    start, user_handler, show_price_list, start_order,
    order_fio, order_phone, order_product, order_quantity,
    order_address, order_comment, confirm_order_callback,
    show_my_orders, show_referral, show_help
)

# Обработчики администратора
from handlers.admin import (
    admin_handler, price_menu_callback, show_products_for_edit,
    edit_product_select, edit_product_field, edit_product_value,
    show_products_for_delete, delete_product, show_products_for_toggle,
    toggle_stock, add_product_name, add_product_category,
    add_product_price, add_product_stock, add_product_photo,
    orders_menu_callback, show_orders_today, show_orders_month,
    show_order_details, change_status_menu, set_order_status,
    back_to_orders, period_start, period_end,
    search_client, send_message_to_user, send_message_text,
    broadcast_text, broadcast_confirm, export_to_google,
    import_from_google, import_products_callback, show_stats,
    admin_back_callback
)

# Обработчики суперадминистратора
from handlers.superadmin import (
    superadmin_handler, show_managers_menu, managers_menu_callback,
    add_manager_id, show_managers_list, show_managers_for_remove,
    remove_manager, superadmin_back_callback
)

# Общие обработчики (выход, назад)
from handlers.common import exit_handler
from handlers.back_handlers import back_button_handler, back_to_admin, back_to_superadmin

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация БД
db_path = os.getenv("DB_PATH", "shop.db")
db = Database(db_name=db_path)

async def error_handler(update, context):
    """Глобальный обработчик ошибок"""
    logger.error(f"❌ Ошибка: {context.error}", exc_info=context.error)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла внутренняя ошибка. Администраторы уже уведомлены."
            )
    except:
        pass

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск бота...")
    
    # Создание приложения
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем глобальный обработчик ошибок
    app.add_error_handler(error_handler)
    
    # ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handler)],
            ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler)],
            SUPERADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, superadmin_handler)],
            
            # Управление прайсом
            PRICE_MENU: [CallbackQueryHandler(price_menu_callback, pattern='^price_')],
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            ADD_PRODUCT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_category)],
            ADD_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)],
            ADD_PRODUCT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_stock)],
            ADD_PRODUCT_PHOTO: [
                MessageHandler(filters.PHOTO, add_product_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_photo)
            ],
            
            EDIT_PRODUCT_SELECT: [CallbackQueryHandler(edit_product_select, pattern='^edit_select_')],
            EDIT_PRODUCT_FIELD: [CallbackQueryHandler(edit_product_field, pattern='^edit_field_')],
            EDIT_PRODUCT_VALUE: [
                MessageHandler(filters.PHOTO, edit_product_value),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_value)
            ],
            
            DELETE_PRODUCT_SELECT: [CallbackQueryHandler(delete_product, pattern='^delete_')],
            TOGGLE_STOCK_SELECT: [CallbackQueryHandler(toggle_stock, pattern='^toggle_')],
            
            # Управление заказами
            ORDERS_MENU: [CallbackQueryHandler(orders_menu_callback, pattern='^orders_')],
            PERIOD_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, period_start)],
            PERIOD_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, period_end)],
            
            # Управление клиентами
            SEARCH_CLIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_client)],
            SEND_MESSAGE: [
                CallbackQueryHandler(send_message_to_user, pattern='^message_user_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_text)
            ],
            
            # Рассылка
            BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_text)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(broadcast_confirm, pattern='^broadcast_')],
            
            # Импорт товаров
            IMPORT_PRODUCTS: [CallbackQueryHandler(import_products_callback, pattern='^import_')],
            
            # Управление менеджерами
            VIEW_MANAGERS: [CallbackQueryHandler(managers_menu_callback, pattern='^manager_')],
            ADD_MANAGER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_manager_id)],
            REMOVE_MANAGER_ID: [CallbackQueryHandler(remove_manager, pattern='^remove_manager_')],
            
            # Оформление заказа
            ORDER_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_fio)],
            ORDER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone)],
            ORDER_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_product)],
            ORDER_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_quantity)],
            ORDER_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_address)],
            ORDER_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_comment)],
            ORDER_CONFIRM: [CallbackQueryHandler(confirm_order_callback, pattern='^(confirm_order|cancel_order)$')],
        },
        fallbacks=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex('^🚪 Выход$'), exit_handler)
        ],
        allow_reentry=True,
        per_message=False
    )
    
    # Добавляем ConversationHandler
    app.add_handler(conv_handler)
    
    # ===== ОБРАБОТЧИКИ ВНЕ CONVERSATIONHANDLER =====
    # Эти обработчики работают в любом состоянии
    
    # Детали заказа и статусы
    app.add_handler(CallbackQueryHandler(show_order_details, pattern='^view_order_'))
    app.add_handler(CallbackQueryHandler(change_status_menu, pattern='^change_status_'))
    app.add_handler(CallbackQueryHandler(set_order_status, pattern='^set_status_'))
    app.add_handler(CallbackQueryHandler(back_to_orders, pattern='^back_to_orders$'))
    
    # Кнопки "Назад"
    app.add_handler(CallbackQueryHandler(back_button_handler, pattern='^back_to_main$'))
    app.add_handler(CallbackQueryHandler(back_to_admin, pattern='^admin_back$'))
    app.add_handler(CallbackQueryHandler(back_to_superadmin, pattern='^superadmin_back$'))
    
    logger.info("✅ БОТ ГОТОВ К РАБОТЕ!")
    
    # Просто запускаем бота - вебхук удалится автоматически
    app.run_polling()

if __name__ == '__main__':
    main()