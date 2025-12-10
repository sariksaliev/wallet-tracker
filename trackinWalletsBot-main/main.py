from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ConversationHandler
)

from datetime import time
import pytz
import bot_handlers
# Конфігурація
import config
from config import ADD_ADDRESS, REMOVE_ADDRESS, REMOVE_CONFIRM, TODAY_WALLET_CHOICE, ADD_SHORTNAME, ADD_NETWORK
from config import logger, TELEGRAM_TOKEN, ANKR_API_KEY
# Класи та функції
from db_manager import DatabaseManager
from etherscan_api import EtherscanAPI
from trongrid_api import TronGridAPI


# Функція для виходу з діалогу
async def cancel(update, context):
    await update.message.reply_text("Действие отменено.", reply_markup=bot_handlers.get_main_menu())
    context.user_data.clear()
    return ConversationHandler.END


def main():
    import logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Запуск бота...")

    # 1. Ініціалізація сервісів
    try:
        db = DatabaseManager()
    except Exception as e:
        logger.critical(f"❌ Не удалось инициализировать базу данных: {e}")
        return

    # 2. Створення програми
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    bot = application.bot

    # 3. Збереження сервісів у bot_data
    application.bot_data['db'] = db
    application.bot_data['api_class'] = EtherscanAPI
    application.bot_data['api_key'] = config.ETHERSCAN_API_KEY
    application.bot_data['tron_api_key'] = config.TRON_API_KEY
    application.bot_data['ankr_api_key'] = ANKR_API_KEY  # Добавляем ANKR ключ

    # ИНИЦИАЛИЗАЦИЯ TRON API
    try:
        application.bot_data['tron_api'] = TronGridAPI(api_key=config.TRON_API_KEY)
        logger.info("✅ TronGrid API успешно инициализирован")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось инициализировать TronGrid API: {e}")
        application.bot_data['tron_api'] = None
        logger.info("ℹ️ TRON сеть будет пропущена из-за проблем с API")

    cancel_filter = filters.Regex('^(Назад|Отменить|Отмена|Відмінити|Cancel)$')

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^Добавить кошелек$'), bot_handlers.add_wallet_start),
            MessageHandler(filters.Regex('^Удалить кошелек$'), bot_handlers.remove_wallet_start),
            MessageHandler(filters.Regex('^Суммы за день$'), bot_handlers.today_incomes_multi_chain),
            MessageHandler(filters.TEXT & (~filters.COMMAND) &
                           (~filters.Regex('^Добавить кошелек$')) &
                           (~filters.Regex('^Удалить кошелек$')) &
                           (~filters.Regex('^Суммы за день$')) &
                           (~filters.Regex('^Мои кошельки$')) &
                           (~filters.Regex('^Помощь$')),
                           bot_handlers.handle_buttons),
        ],
        states={
            ADD_NETWORK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, bot_handlers.add_wallet_network)
            ],
            ADD_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, bot_handlers.add_wallet_address)],
            ADD_SHORTNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, bot_handlers.add_wallet_shortname)],
            REMOVE_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, bot_handlers.remove_wallet_address)],
            REMOVE_CONFIRM: [
                MessageHandler(filters.Regex('^УДАЛИТЬ$'), bot_handlers.remove_wallet_confirm),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, bot_handlers.remove_wallet_confirm)
            ],
            TODAY_WALLET_CHOICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, bot_handlers.today_wallet_choice)
            ],
        },
        fallbacks=[
            CommandHandler('start', bot_handlers.start),
            CommandHandler('cancel', cancel),
            MessageHandler(cancel_filter, cancel)
        ]
    )

    # 5. Реєстрація обробників
    application.add_handler(CommandHandler('start', bot_handlers.start))
    application.add_handler(CommandHandler('my_wallets', bot_handlers.list_wallets))
    application.add_handler(CommandHandler('today', bot_handlers.today_incomes_multi_chain))
    application.add_handler(CommandHandler('help', bot_handlers.help_command))
    application.add_handler(conv_handler)

    # Добавляем обработчики для кнопок меню (чтобы работали вне ConversationHandler)
    application.add_handler(MessageHandler(filters.Regex('^Мои кошельки$'), bot_handlers.list_wallets))
    application.add_handler(MessageHandler(filters.Regex('^Помощь$'), bot_handlers.help_command))

    # 6. Запуск планувальника у фоновому потоці
    # Время 00:00 по UTC+3 = 21:00 по UTC
    job_time_midnight = time(hour=21, minute=0, second=0, tzinfo=pytz.UTC)
    application.job_queue.run_daily(bot_handlers.process_today_incomes_job, time=job_time_midnight,
                                    days=(0, 1, 2, 3, 4, 5, 6))

    # Альтернативно, для отладки, можно запускать каждый час:
    # application.job_queue.run_repeating(bot_handlers.process_today_incomes_job, interval=3600, first=10)

    # 7. Запуск бота
    logger.info("🚀 Бот запущен!")
    logger.info(f"✅ Поддерживаемые сети: {len(config.SUPPORTED_CHAINS)}")
    logger.info(f"✅ ANKR API ключ: {'Установлен' if ANKR_API_KEY else 'Отсутствует'}")

    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("⛔️ Бот остановлен вручную.")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка бота: {e}")
    finally:
        db.close()
        logger.info("✅ Соединение с БД закрыто. Бот завершил работу.")


if __name__ == '__main__':
    main()