from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ConversationHandler
)

from datetime import time
import pytz
import bot_handlers
# Конфігурація
import config
from config import ADD_ADDRESS, REMOVE_ADDRESS, REMOVE_CONFIRM, TODAY_WALLET_CHOICE, ADD_SHORTNAME, ADD_NETWORK
from config import logger, TELEGRAM_TOKEN
# Класи та функції
from db_manager import DatabaseManager
from etherscan_api import EtherscanAPI
from trongrid_api import TronGridAPI
from bsc_rpc_api import BscRPC, BscRPCError


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

    application.bot_data['tron_api'] = TronGridAPI
    application.bot_data['tron_api_key'] = config.TRON_API_KEY

    # ИНИЦИАЛИЗАЦИЯ BSC RPC С ОБРАБОТКОЙ ОШИБОК
    try:
        application.bot_data['bsc_rpc'] = BscRPC()
        logger.info("✅ BSC RPC успешно инициализирован")
    except BscRPCError as e:
        logger.warning(f"⚠️ Не удалось инициализировать BSC RPC: {e}")
        application.bot_data['bsc_rpc'] = None
        logger.info("ℹ️ BNB Chain будет пропущен из-за проблем с RPC")
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка при инициализации BSC RPC: {e}")
        application.bot_data['bsc_rpc'] = None

    cancel_filter = filters.Regex('^(Назад|Отменить)$')

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^Добавить кошелек$'), bot_handlers.add_wallet_start),
            MessageHandler(filters.Regex('^Удалить кошелек$'), bot_handlers.remove_wallet_start),
            MessageHandler(filters.Regex('^Суммы за день$'), bot_handlers.today_incomes_multi_chain),
            MessageHandler(filters.TEXT & (~filters.COMMAND) &
                           (~filters.Regex('^Добавить кошелек$')) &
                           (~filters.Regex('^Удалить кошелек$')) &
                           (~filters.Regex('^Суммы за день$')),
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

    # 6. Запуск планувальника у фоновому потоці
    job_time_midnight = time(hour=21, minute=0, second=0, tzinfo=pytz.UTC)
    application.job_queue.run_daily(bot_handlers.process_today_incomes_job, time=job_time_midnight,
                                    days=(0, 1, 2, 3, 4, 5, 6))

    # 7. Запуск бота
    logger.info("🚀 Бот запущен!")
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("⛔️ Бот остановлен вручную.")
    finally:
        db.close()
        logger.info("✅ Соединение с БД закрыто. Бот завершил работу.")


if __name__ == '__main__':
    main()