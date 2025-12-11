import re
from datetime import datetime, timedelta
import pytz
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from web3 import Web3

from config import ADD_ADDRESS, REMOVE_ADDRESS, REMOVE_CONFIRM, TODAY_WALLET_CHOICE, ADD_SHORTNAME, ADD_NETWORK, \
    TRON_API_KEY, TRON_EXPLORER, TRC20_SYMBOLS, logger
from config import TZ_UTC_PLUS_3, CHAIN_TOKENS, SUPPORTED_CHAINS, EXPLORERS, ANKR_API_KEY
from etherscan_api import EtherscanAPI, EtherscanAPIError
from trongrid_api import TronGridAPI
from tracker_factory import TrackerFactory  # Используем фабрику трекеров


# --- Вспомогательные функции ---

def is_valid_address(address: str) -> bool:
    """Проверяет валидность адреса Ethereum."""
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


def get_main_menu() -> ReplyKeyboardMarkup:
    """Возвращает главное меню."""
    keyboard = [['Добавить кошелек', 'Удалить кошелек'],
                ['Мои кошельки', 'Суммы за день'],
                ['Помощь']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# --- Основные обработчики команд ---

async def start(update: Update, context: CallbackContext):
    """Обработчик команды /start."""
    await update.message.reply_text(
        'Привет! 👋 Я бот для отслеживания поступлений на кошелек.\n\n'
        '📅 Каждый день в 00:00 (UTC+3) я отправляю отчет с входящими транзакциями за прошедший день.\n'
        'Выберите действие из меню:',
        reply_markup=get_main_menu()
    )


async def list_wallets(update: Update, context: CallbackContext):
    """Показывает список кошельков пользователя."""
    db = context.bot_data['db']
    user_id = update.message.from_user.id
    wallets = db.get_wallets(user_id)

    if not wallets:
        await update.message.reply_text(
            'У вас нет добавленных кошельков.\n'
            'Нажмите "Добавить кошелек", чтобы начать.',
            reply_markup=get_main_menu()
        )
        return

    message = "📋 Ваши кошельки:\n\n"
    for i, (addr, shortname, network) in enumerate(wallets, 1):
        network_display = network.upper()
        if network == 'bnb':
            network_display = 'BNB Chain'
        elif network == 'eth':
            network_display = 'Ethereum'
        elif network == 'tron':
            network_display = 'TRON'

        message += f"{i}. `{addr[:6]}...{addr[-4:]}` ({shortname}) - {network_display}\n"

    message += "\n📊 Отчет поступлений отправляется ежедневно в 00:00 (UTC+3)."
    await update.message.reply_text(message, reply_markup=get_main_menu(), parse_mode='Markdown')


async def today_incomes_multi_chain(update: Update, context: CallbackContext):
    """Начало проверки поступлений за сегодня."""
    db = context.bot_data['db']
    user_id = update.message.from_user.id
    wallets = db.get_wallets(user_id)

    if not wallets:
        await update.message.reply_text(
            'ℹ️ У вас нет добавленных кошельков.',
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    # Формируем сообщение со списком кошельков
    message = '📊 Выберите кошелек для проверки поступлений за сегодня\n\n'
    message += 'Введите полный адрес или короткий формат одного из ваших кошельков:\n\n'
    for addr, shortname, network in wallets:
        network_display = network.upper()
        if network == 'bnb':
            network_display = 'BNB Chain'
        elif network == 'eth':
            network_display = 'Ethereum'
        elif network == 'tron':
            network_display = 'TRON'

        message += f"• `{addr[:6]}...{addr[-4:]}` ({shortname}) - {network_display}\n"

    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return TODAY_WALLET_CHOICE


async def today_wallet_choice(update: Update, context: CallbackContext):
    """Обработка выбранного кошелька для проверки поступлений."""
    db = context.bot_data['db']
    user_id = update.message.from_user.id
    selected_address = update.message.text.strip()

    # Проверяем, введен ли адрес или короткий идентификатор
    wallets = db.get_wallets(user_id)
    wallet_data = None

    # Сначала ищем по полному адресу
    for addr, shortname, network in wallets:
        if addr.lower() == selected_address.lower():
            wallet_data = (addr, shortname, network)
            break

    # Если не нашли по полному адресу, ищем по короткому формату
    if not wallet_data:
        for addr, shortname, network in wallets:
            short_addr = f"{addr[:6]}...{addr[-4:]}"
            if short_addr.lower() == selected_address.lower():
                wallet_data = (addr, shortname, network)
                break

    if not wallet_data:
        await update.message.reply_text(
            '❌ Введенный адрес не относится к вашим кошелькам. Попробуйте снова.',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
        )
        return TODAY_WALLET_CHOICE

    wallet_address, shortname, network = wallet_data

    # Сохраняем выбранный адрес в context.user_data
    context.user_data['selected_wallet'] = wallet_address
    context.user_data['network'] = network

    # Получаем транзакции за сегодня
    now_utc3 = datetime.now(TZ_UTC_PLUS_3)
    today_start = now_utc3.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    ts_start = int(today_start.timestamp())
    ts_end = int(today_end.timestamp())

    await update.message.reply_text(
        f'🔄 Получаю поступления за сегодня для кошелька `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname})...',
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )

    try:
        # Получаем транзакции через фабрику трекеров
        all_transactions, token_sums = await fetch_today_transactions_factory(
            context=context,
            wallet_address=wallet_address,
            shortname=shortname,
            network=network,
            ts_start=ts_start,
            ts_end=ts_end
        )

        if not all_transactions:
            await update.message.reply_text(
                "💸 Сегодня не было поступлений для этого кошелька.",
                reply_markup=get_main_menu()
            )
            context.user_data.clear()
            return ConversationHandler.END

        # Отправляем транзакции
        await send_transactions(
            update=update,
            transactions=all_transactions,
            token_sums=token_sums,
            wallet_address=wallet_address,
            shortname=shortname,
            is_today_check=True,
            today_start=today_start
        )

    except Exception as e:
        logger.error(f"Ошибка при получении транзакций: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при получении транзакций. Попробуйте позже.",
            reply_markup=get_main_menu()
        )

    context.user_data.clear()
    return ConversationHandler.END


async def fetch_today_transactions_factory(context, wallet_address, shortname, network, ts_start, ts_end):
    """Получает транзакции за указанный период через фабрику трекеров."""
    all_transactions = []
    token_sums = {}

    try:
        # Создаем трекер через фабрику
        tracker_kwargs = {
            'etherscan_api_key': context.bot_data['api_key'],
            'tron_api_key': context.bot_data.get('tron_api_key', TRON_API_KEY),
            'ankr_api_key': ANKR_API_KEY
        }

        # Для Ethereum сетей указываем chain_id
        if network == 'eth':
            # Обрабатываем все поддерживаемые сети
            for chain_id, chain_name in SUPPORTED_CHAINS.items():
                if chain_id == 'tron':
                    continue  # TRON обрабатываем отдельно

                try:
                    # Создаем трекер для каждой сети
                    if chain_id == 56:  # BNB Chain
                        tracker = TrackerFactory.create_tracker('bnb', **tracker_kwargs)
                    elif chain_id == 1:  # Ethereum
                        tracker = TrackerFactory.create_tracker('eth', **{**tracker_kwargs, 'chain_id': chain_id})
                    else:
                        # Для других сетей определяем название
                        network_name = CHAIN_TOKENS.get(chain_id, 'eth').lower()
                        if network_name in ['eth', 'bnb', 'tron']:
                            # Уже обработали
                            continue
                        tracker = TrackerFactory.create_tracker(network_name, **tracker_kwargs)

                    # Получаем транзакции
                    result = tracker.get_transactions(
                        address=wallet_address,
                        start_time=ts_start,
                        end_time=ts_end
                    )

                    # Обрабатываем нативные транзакции
                    for tx in result.get('native', []):
                        if tx.get('to', '').lower() == wallet_address.lower():
                            amount = tx.get('value', 0)
                            token = tx.get('token', CHAIN_TOKENS.get(chain_id, 'UNKNOWN'))

                            all_transactions.append({
                                'chain_id': chain_id,
                                'chain_name': chain_name,
                                'wallet': wallet_address,
                                'amount': amount,
                                'token': token,
                                'sender': tx.get('from', ''),
                                'timestamp': tx.get('timestamp', 0),
                                'hash': tx.get('hash', '')
                            })
                            token_sums[token] = token_sums.get(token, 0) + amount

                    # Обрабатываем токенные транзакции
                    for tx in result.get('tokens', []):
                        if tx.get('to', '').lower() == wallet_address.lower():
                            amount = tx.get('value', 0)
                            if amount <= 0.01:
                                continue

                            token = tx.get('token_symbol', tx.get('token', 'UNKNOWN'))

                            all_transactions.append({
                                'chain_id': chain_id,
                                'chain_name': chain_name,
                                'wallet': wallet_address,
                                'amount': amount,
                                'token': token,
                                'sender': tx.get('from', ''),
                                'timestamp': tx.get('timestamp', 0),
                                'hash': tx.get('hash', '')
                            })
                            token_sums[token] = token_sums.get(token, 0) + amount

                except Exception as e:
                    logger.error(f"Ошибка обработки сети {chain_id} ({chain_name}): {e}")
                    continue

        elif network == 'bnb':
            # Обрабатываем BNB Chain отдельно
            try:
                tracker = TrackerFactory.create_tracker('bnb', **tracker_kwargs)
                result = tracker.get_transactions(
                    address=wallet_address,
                    start_time=ts_start,
                    end_time=ts_end
                )

                # Обрабатываем нативные BNB транзакции
                for tx in result.get('native', []):
                    if tx.get('to', '').lower() == wallet_address.lower():
                        amount = tx.get('value', 0)
                        token = tx.get('token', 'BNB')

                        all_transactions.append({
                            'chain_id': 56,
                            'chain_name': 'BNB Smart Chain',
                            'wallet': wallet_address,
                            'amount': amount,
                            'token': token,
                            'sender': tx.get('from', ''),
                            'timestamp': tx.get('timestamp', 0),
                            'hash': tx.get('hash', '')
                        })
                        token_sums[token] = token_sums.get(token, 0) + amount

                # Обрабатываем BEP20 транзакции
                for tx in result.get('tokens', []):
                    if tx.get('to', '').lower() == wallet_address.lower():
                        amount = tx.get('value', 0)
                        if amount <= 0.01:
                            continue

                        token = tx.get('token_symbol', 'UNKNOWN')

                        all_transactions.append({
                            'chain_id': 56,
                            'chain_name': 'BNB Smart Chain',
                            'wallet': wallet_address,
                            'amount': amount,
                            'token': token,
                            'sender': tx.get('from', ''),
                            'timestamp': tx.get('timestamp', 0),
                            'hash': tx.get('hash', '')
                        })
                        token_sums[token] = token_sums.get(token, 0) + amount

            except Exception as e:
                logger.error(f"Ошибка обработки BNB Chain: {e}")

        elif network == 'tron':
            # TRON обрабатываем отдельно
            tracker = TrackerFactory.create_tracker('tron', **tracker_kwargs)
            result = tracker.get_transactions(
                address=wallet_address,
                start_time=ts_start,
                end_time=ts_end
            )

            # Обрабатываем нативные TRX транзакции
            for tx in result.get('native', []):
                if tx.get('to', '').lower() == wallet_address.lower():
                    amount = tx.get('value', 0)

                    all_transactions.append({
                        'chain_id': 'tron',
                        'chain_name': 'TRON',
                        'wallet': wallet_address,
                        'amount': amount,
                        'token': 'TRX',
                        'sender': tx.get('from', ''),
                        'timestamp': tx.get('timestamp', 0),
                        'hash': tx.get('hash', '')
                    })
                    token_sums['TRX'] = token_sums.get('TRX', 0) + amount

            # Обрабатываем TRC20 транзакции
            for tx in result.get('tokens', []):
                if tx.get('to', '').lower() == wallet_address.lower():
                    amount = tx.get('value', 0)
                    if amount <= 0.01:
                        continue

                    token = tx.get('token_symbol', 'UNKNOWN')

                    all_transactions.append({
                        'chain_id': 'tron',
                        'chain_name': 'TRON',
                        'wallet': wallet_address,
                        'amount': amount,
                        'token': token,
                        'sender': tx.get('from', ''),
                        'timestamp': tx.get('timestamp', 0),
                        'hash': tx.get('hash', '')
                    })
                    token_sums[token] = token_sums.get(token, 0) + amount

    except Exception as e:
        logger.error(f"Ошибка в fetch_today_transactions_factory: {e}")
        # Fallback на старый метод если фабрика не работает
        logger.info("Использую старый метод как fallback...")
        all_transactions, token_sums = await fetch_today_transactions_legacy(
            context=context,
            wallet_address=wallet_address,
            shortname=shortname,
            network=network,
            ts_start=ts_start,
            ts_end=ts_end
        )

    return all_transactions, token_sums


async def fetch_today_transactions_legacy(context, wallet_address, shortname, network, ts_start, ts_end):
    """Legacy метод получения транзакций (fallback)."""
    all_transactions = []
    token_sums = {}

    if network == 'eth':
        for chain_id, chain_name in SUPPORTED_CHAINS.items():
            if chain_id == 'tron':
                continue

            try:
                api = EtherscanAPI(api_key=context.bot_data['api_key'], chain_id=chain_id)

                # Нативные транзакции
                native_txs = api.get_chain_transactions(wallet_address) or []
                for tx in native_txs:
                    if (tx.get('to', '').lower() == wallet_address.lower() and
                            ts_start <= int(tx.get('timeStamp', 0)) <= ts_end and
                            int(tx.get('value', 0)) > 0):
                        amount = int(tx['value']) / 1e18
                        token_symbol = CHAIN_TOKENS.get(chain_id, chain_name)
                        all_transactions.append({
                            'chain_id': chain_id,
                            'chain_name': chain_name,
                            'wallet': wallet_address,
                            'amount': amount,
                            'token': token_symbol,
                            'sender': tx.get('from', ''),
                            'timestamp': int(tx['timeStamp']),
                            'hash': tx.get('hash')
                        })
                        token_sums[token_symbol] = token_sums.get(token_symbol, 0) + amount

                # Токенные транзакции
                token_txs = api.get_token_transactions(wallet_address) or []
                for tx in token_txs:
                    if (tx.get('to', '').lower() == wallet_address.lower() and
                            ts_start <= int(tx.get('timeStamp', 0)) <= ts_end and
                            int(tx.get('value', 0)) > 0):
                        token_symbol = tx.get('tokenSymbol', 'UNKNOWN')
                        decimals = int(tx.get('tokenDecimal', 18))
                        amount = int(tx['value']) / (10 ** decimals)

                        if amount <= 0.01:
                            continue

                        all_transactions.append({
                            'chain_id': chain_id,
                            'chain_name': chain_name,
                            'wallet': wallet_address,
                            'amount': amount,
                            'token': token_symbol,
                            'sender': tx.get('from', ''),
                            'timestamp': int(tx['timeStamp']),
                            'hash': tx.get('hash')
                        })
                        token_sums[token_symbol] = token_sums.get(token_symbol, 0) + amount

            except Exception as e:
                logger.error(f"Ошибка обработки сети {chain_id}: {e}")
                continue

    elif network == 'bnb':
        # Для BNB Chain используем chain_id = 56
        try:
            api = EtherscanAPI(api_key=context.bot_data['api_key'], chain_id=56)

            # Нативные BNB транзакции
            native_txs = api.get_chain_transactions(wallet_address) or []
            for tx in native_txs:
                if (tx.get('to', '').lower() == wallet_address.lower() and
                        ts_start <= int(tx.get('timeStamp', 0)) <= ts_end and
                        int(tx.get('value', 0)) > 0):
                    amount = int(tx['value']) / 1e18
                    all_transactions.append({
                        'chain_id': 56,
                        'chain_name': 'BNB Smart Chain',
                        'wallet': wallet_address,
                        'amount': amount,
                        'token': 'BNB',
                        'sender': tx.get('from', ''),
                        'timestamp': int(tx['timeStamp']),
                        'hash': tx.get('hash')
                    })
                    token_sums['BNB'] = token_sums.get('BNB', 0) + amount

            # BEP20 токенные транзакции
            token_txs = api.get_token_transactions(wallet_address) or []
            for tx in token_txs:
                if (tx.get('to', '').lower() == wallet_address.lower() and
                        ts_start <= int(tx.get('timeStamp', 0)) <= ts_end and
                        int(tx.get('value', 0)) > 0):
                    token_symbol = tx.get('tokenSymbol', 'UNKNOWN')
                    decimals = int(tx.get('tokenDecimal', 18))
                    amount = int(tx['value']) / (10 ** decimals)

                    if amount <= 0.01:
                        continue

                    all_transactions.append({
                        'chain_id': 56,
                        'chain_name': 'BNB Smart Chain',
                        'wallet': wallet_address,
                        'amount': amount,
                        'token': token_symbol,
                        'sender': tx.get('from', ''),
                        'timestamp': int(tx['timeStamp']),
                        'hash': tx.get('hash')
                    })
                    token_sums[token_symbol] = token_sums.get(token_symbol, 0) + amount

        except Exception as e:
            logger.error(f"Ошибка обработки BNB Chain: {e}")

    elif network == 'tron':
        try:
            api = TronGridAPI(api_key=context.bot_data.get('tron_api_key', TRON_API_KEY))

            # Нативные TRX транзакции
            native_txs = api.get_chain_transactions(wallet_address) or []
            for tx in native_txs:
                ts_ms = tx.get('raw_data', {}).get('timestamp', 0)
                ts = ts_ms // 1000

                if not (ts_start <= ts <= ts_end):
                    continue

                contract = tx.get('raw_data', {}).get('contract', [{}])[0]
                if contract.get('type') == 'TransferContract':
                    value = contract.get('parameter', {}).get('value', {})
                    to_address = value.get('to_address', '').lower()

                    if to_address == wallet_address.lower() and value.get('amount', 0) > 0:
                        amount_trx = int(value['amount']) / 1e6
                        all_transactions.append({
                            'chain_id': 'tron',
                            'chain_name': 'TRON',
                            'wallet': wallet_address,
                            'amount': amount_trx,
                            'token': 'TRX',
                            'sender': value.get('owner_address', ''),
                            'timestamp': ts,
                            'hash': tx.get('txID')
                        })
                        token_sums['TRX'] = token_sums.get('TRX', 0) + amount_trx

            # TRC20 транзакции
            trc20_transfers = api.get_trc20_transfers(wallet_address) or []
            for transfer in trc20_transfers:
                timestamp = transfer.get('block_timestamp', 0) // 1000

                if not (ts_start <= timestamp <= ts_end):
                    continue

                to_addr = transfer.get('to', '').lower()
                if to_addr != wallet_address.lower():
                    continue

                token_info = transfer.get('token_info', {})
                symbol = token_info.get('symbol', 'UNKNOWN')
                decimals = int(token_info.get('decimals', 6))
                amount_raw = int(transfer.get('value', 0))
                amount = amount_raw / (10 ** decimals)

                if amount <= 0:
                    continue

                all_transactions.append({
                    'chain_id': 'tron',
                    'chain_name': 'TRON',
                    'wallet': wallet_address,
                    'amount': amount,
                    'token': symbol,
                    'sender': transfer.get('from', ''),
                    'timestamp': timestamp,
                    'hash': transfer.get('transaction_id', '')
                })
                token_sums[symbol] = token_sums.get(symbol, 0) + amount

        except Exception as e:
            logger.error(f"Ошибка обработки TRON: {e}")

    return all_transactions, token_sums


async def send_transactions(update, transactions, token_sums, wallet_address, shortname, is_today_check=False,
                            today_start=None):
    """Отправляет транзакции пользователю."""
    if not transactions:
        return

    # Сортируем по времени
    transactions.sort(key=lambda x: x['timestamp'])

    # Разбиваем на части для отправки
    chunk_size = 10 if is_today_check else 20
    chunks = [transactions[i:i + chunk_size] for i in range(0, len(transactions), chunk_size)]

    for chunk_idx, chunk in enumerate(chunks):
        if is_today_check and today_start:
            msg = f"📊 Поступления с 00:00 до {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S')} ({today_start.strftime('%Y-%m-%d')}) для кошелька `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname}) (UTC+3)\n\n"
        else:
            msg = f"📊 Поступления за {today_start.strftime('%Y-%m-%d')} для кошелька `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname}) (UTC+3)\n\n"

        for tx in chunk:
            short_sender = f"{tx['sender'][:6]}...{tx['sender'][-4:]}" if tx['sender'] else "Unknown"
            tx_time = datetime.fromtimestamp(tx['timestamp'], TZ_UTC_PLUS_3).strftime('%H:%M:%S')

            # Формируем ссылку на explorer
            if tx['chain_id'] == 'tron':
                explorer_url = TRON_EXPLORER.format(tx['hash'])
            else:
                explorer_template = EXPLORERS.get(tx['chain_id'], "https://etherscan.io/tx/{}")
                explorer_url = explorer_template.format(tx['hash'])

            msg += (f"• {tx['chain_name']}: {tx['amount']:.6f} {tx['token']}\n"
                    f"  От: `{short_sender}`\n"
                    f"  Время: {tx_time}\n"
                    f"  🔗 [Транзакция]({explorer_url})\n\n")

        msg += f"🕒 Обновлено: {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S UTC+3')}"

        if is_today_check:
            await update.message.reply_text(
                msg,
                reply_markup=get_main_menu(),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            await update.context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=msg,
                reply_markup=get_main_menu(),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

    # Отправляем итоговую сумму
    if token_sums:
        if is_today_check:
            sums_msg = f"💰 Итоговая сумма поступлений с 00:00 до {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S')} ({today_start.strftime('%Y-%m-%d')}) для кошелька `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname}) (UTC+3)\n\n"
        else:
            sums_msg = f"💰 Итоговая сумма поступлений за {today_start.strftime('%Y-%m-%d')} для кошелька `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname}) (UTC+3)\n\n"

        # Сортируем по убыванию суммы
        for token, total in sorted(token_sums.items(), key=lambda x: x[1], reverse=True):
            sums_msg += f"• {token}: {total:.6f}\n"

        sums_msg += f"\n🕒 Обновлено: {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S UTC+3')}"

        if is_today_check:
            await update.message.reply_text(
                sums_msg,
                reply_markup=get_main_menu(),
                parse_mode='Markdown'
            )
        else:
            await update.context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=sums_msg,
                reply_markup=get_main_menu(),
                parse_mode='Markdown'
            )


async def process_today_incomes_job(context):
    """Ежедневная отправка отчетов."""
    db = context.bot_data['db']
    api_key = context.bot_data['api_key']

    users = db.get_all_users()
    if not users:
        return

    now_utc3 = datetime.now(TZ_UTC_PLUS_3)
    today_start = now_utc3.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    today_end = today_start + timedelta(days=1)
    ts_start = int(today_start.timestamp())
    ts_end = int(today_end.timestamp())

    for user_id in users:
        try:
            wallets = db.get_wallets(user_id)
            if not wallets:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="ℹ️ У вас нет добавленных кошельков.",
                    reply_markup=get_main_menu()
                )
                continue

            # Отправляем список кошельков пользователя
            wallets_msg = f"📋 Ваши добавленные кошельки ({today_start.strftime('%Y-%m-%d')}):\n\n"
            for wallet_address, shortname, network in wallets:
                network_display = network.upper()
                if network == 'bnb':
                    network_display = 'BNB Chain'
                elif network == 'eth':
                    network_display = 'Ethereum'
                elif network == 'tron':
                    network_display = 'TRON'

                wallets_msg += f"• `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname}) - {network_display}\n"
            wallets_msg += f"\n🕒 Отчет за: {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S UTC+3')}"

            await context.bot.send_message(
                chat_id=user_id,
                text=wallets_msg,
                reply_markup=get_main_menu(),
                parse_mode='Markdown'
            )

            # Обрабатываем каждый кошелек отдельно
            for wallet_address, shortname, network in wallets:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f'🔄 Получаю поступления за {today_start.strftime("%Y-%m-%d")} для кошелька `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname})...',
                    reply_markup=get_main_menu(),
                    parse_mode='Markdown'
                )

                try:
                    all_transactions, token_sums = await fetch_today_transactions_factory(
                        context=context,
                        wallet_address=wallet_address,
                        shortname=shortname,
                        network=network,
                        ts_start=ts_start,
                        ts_end=ts_end
                    )

                    if not all_transactions:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"💸 Не было поступлений за {today_start.strftime('%Y-%m-%d')} для кошелька `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname}).",
                            reply_markup=get_main_menu(),
                            parse_mode='Markdown'
                        )
                        continue

                    # Используем фиктивный update для отправки
                    class DummyUpdate:
                        def __init__(self, chat_id):
                            self.effective_chat = type('obj', (object,), {'id': chat_id})
                            self.context = context

                    dummy_update = DummyUpdate(user_id)

                    await send_transactions(
                        update=dummy_update,
                        transactions=all_transactions,
                        token_sums=token_sums,
                        wallet_address=wallet_address,
                        shortname=shortname,
                        is_today_check=False,
                        today_start=today_start
                    )

                except Exception as e:
                    logger.error(f"Ошибка обработки кошелька {wallet_address} для пользователя {user_id}: {e}")
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Ошибка при получении транзакций для кошелька `{wallet_address[:6]}...{wallet_address[-4:]}` ({shortname}).",
                        reply_markup=get_main_menu(),
                        parse_mode='Markdown'
                    )

        except Exception as e:
            logger.error(f"Ошибка обработки пользователя {user_id}: {e}")
            continue


async def help_command(update: Update, context: CallbackContext):
    """Показывает справку."""
    help_text = """
🔧 Как пользоваться ботом:

1️⃣ Добавить кошелек: 
• Нажмите "Добавить кошелек" 
• Выберите сеть (ETH, BNB или TRON)
• Введите адрес кошелька
• Введите название кошелька

2️⃣ Удалить кошелек: 
• Нажмите "Удалить кошелек" 
• Введите адрес кошелька
• Подтвердите удаление

3️⃣ Мои кошельки:
• Показывает список всех добавленных кошельков

4️⃣ Суммы за день: 
• Показывает поступления за сегодня для выбранного кошелька

5️⃣ Ежедневный отчет:
• Отправляется автоматически каждый день в 00:00 (UTC+3)

📝 Поддерживаемые сети:
• Ethereum (ETH, USDT, USDC и другие ERC20 токены)
• BNB Chain (BNB, BUSD, USDT и другие BEP20 токены)
• Polygon (MATIC, USDT и другие токены)
• TRON (TRX, USDT-TRON и другие TRC20 токены)
"""
    await update.message.reply_text(help_text, reply_markup=get_main_menu(), parse_mode='Markdown')


def is_valid_tron_address(address: str) -> bool:
    """Проверяет валидность TRON-адреса (Base58 или hex)."""
    try:
        if address.startswith('T') and len(address) == 34:
            return True
        elif address.startswith('41') and len(address) == 42:
            bytes.fromhex(address[2:])
            return True
        return False
    except Exception as e:
        return False


async def add_wallet_start(update: Update, context: CallbackContext):
    """Начало добавления кошелька."""
    keyboard = [['ETH', 'BNB', 'TRON'], ['Отменить']]
    await update.message.reply_text(
        '➕ Добавление кошелька\n\n'
        'Выберите сеть:',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return ADD_NETWORK


async def add_wallet_network(update: Update, context: CallbackContext):
    """Обработка выбора сети."""
    network_choice = update.message.text.strip().lower()

    if network_choice == 'eth':
        context.user_data['pending_network'] = 'eth'
        await update.message.reply_text(
            '📥 Введите адрес ETH-кошелька (начинается с 0x):',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADD_ADDRESS

    elif network_choice == 'bnb':
        context.user_data['pending_network'] = 'bnb'
        await update.message.reply_text(
            '📥 Введите адрес BNB Chain кошелька (начинается с 0x):',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADD_ADDRESS

    elif network_choice == 'tron':
        context.user_data['pending_network'] = 'tron'
        await update.message.reply_text(
            '📥 Введите адрес TRON-кошелька (начинается с T или 41):',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADD_ADDRESS
    else:
        await update.message.reply_text(
            '❌ Некоректный выбор сети. Выберите ETH, BNB или TRON.',
            reply_markup=ReplyKeyboardMarkup([['ETH', 'BNB', 'TRON'], ['Отменить']], resize_keyboard=True,
                                             one_time_keyboard=True)
        )
        return ADD_NETWORK


async def add_wallet_address(update: Update, context: CallbackContext):
    """Обработка ввода адреса кошелька."""
    wallet_address = update.message.text.strip()
    user_id = update.message.from_user.id
    db = context.bot_data['db']
    network = context.user_data.get('pending_network', 'eth')

    # Проверка валидности адреса
    if network in ['eth', 'bnb']:
        if not Web3.is_address(wallet_address):
            await update.message.reply_text(
                '❌ Недействительный адрес!\n\n'
                'Адрес должен:\n'
                '• Начинаться с `0x`\n'
                '• Содержать 42 символа\n'
                '• Состоять из символов (0-9, a-f, A-F)',
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
            )
            return ADD_ADDRESS
    elif network == 'tron':
        if not is_valid_tron_address(wallet_address):
            await update.message.reply_text(
                '❌ Недействительный адрес TRON!\n\n'
                'Адрес должен:\n'
                '• Начинаться с `T` (Base58, 34 символа) или\n'
                '• Начинаться с `41` (hex, 42 символа)',
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
            )
            return ADD_ADDRESS

    # Проверка, не добавлен ли уже такой адрес
    wallets = db.get_wallets(user_id)
    existing_addresses = [(addr.lower(), net) for addr, shortname, net in wallets]
    if (wallet_address.lower(), network) in existing_addresses:
        await update.message.reply_text(
            '❌ Этот адрес уже добавлен в этой сети!\n\n'
            'Введите другой адрес или выберите "Отменить".',
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADD_ADDRESS

    context.user_data['pending_wallet_address'] = wallet_address
    await update.message.reply_text(
        f'📝 Введите короткое название для кошелька {network.upper()}.\n'
        'Название должно быть уникальным (только латинские буквы, цифры и пробелы):',
        reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return ADD_SHORTNAME


async def add_wallet_shortname(update: Update, context: CallbackContext):
    """Обработка ввода названия кошелька."""
    shortname = update.message.text.strip()
    user_id = update.message.from_user.id
    wallet_address = context.user_data.get('pending_wallet_address')
    network = context.user_data.get('pending_network', 'eth')
    db = context.bot_data['db']

    if not wallet_address:
        await update.message.reply_text(
            'Ошибка: адрес кошелька не найден. Начните добавление заново.',
            reply_markup=get_main_menu()
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Проверка длины названия
    if len(shortname) > 20 or len(shortname) < 1:
        await update.message.reply_text(
            'Короткое название должно быть от 1 до 20 символов. Попробуйте еще раз:',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
            parse_mode='Markdown'
        )
        return ADD_SHORTNAME

    # Проверка символов в названии
    if not re.fullmatch(r'[a-zA-Z0-9 ]+', shortname):
        await update.message.reply_text(
            'Короткое название может содержать только латинские буквы (a-z, A-Z), цифры (0-9) и пробелы.\n'
            'Попробуйте еще раз:',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
            parse_mode='Markdown'
        )
        return ADD_SHORTNAME

    # Добавляем кошелек в базу данных
    if db.add_wallet(user_id, wallet_address, shortname, network):
        short_wallet = f"{wallet_address[:6]}...{wallet_address[-4:]}"
        network_display = network.upper()
        if network == 'bnb':
            network_display = 'BNB Chain'
        elif network == 'eth':
            network_display = 'Ethereum'
        elif network == 'tron':
            network_display = 'TRON'

        await update.message.reply_text(
            f'✅ Кошелек `{short_wallet}` ({shortname}) в сети {network_display} успешно добавлен!',
            reply_markup=get_main_menu(),
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END
    else:
        network_display = network.upper()
        if network == 'bnb':
            network_display = 'BNB Chain'
        elif network == 'eth':
            network_display = 'Ethereum'
        elif network == 'tron':
            network_display = 'TRON'

        await update.message.reply_text(
            f'❌ Кошелек с адресом `{wallet_address[:6]}...{wallet_address[-4:]}` или названием `{shortname}` '
            f'в сети {network_display} уже используется! Попробуйте другое название.',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
            parse_mode='Markdown'
        )
        return ADD_SHORTNAME


async def remove_wallet_start(update: Update, context: CallbackContext):
    """Начало удаления кошелька."""
    db = context.bot_data['db']
    user_id = update.message.from_user.id
    wallets = db.get_wallets(user_id)

    if not wallets:
        await update.message.reply_text(
            'ℹ️ У вас нет кошельков для удаления.',
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    message = '🗑️ Удаление кошелька\n\n'
    message += 'Введите полный адрес или короткий формат одного из ваших кошельков:\n\n'
    for addr, shortname, network in wallets:
        network_display = network.upper()
        if network == 'bnb':
            network_display = 'BNB Chain'
        elif network == 'eth':
            network_display = 'Ethereum'
        elif network == 'tron':
            network_display = 'TRON'

        message += f"• `{addr[:6]}...{addr[-4:]}` ({shortname}) - {network_display}\n"

    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return REMOVE_ADDRESS


async def remove_wallet_address(update: Update, context: CallbackContext):
    """Обработка ввода адреса для удаления."""
    address = update.message.text.strip()
    user_id = update.message.from_user.id
    db = context.bot_data['db']

    wallets = db.get_wallets(user_id)
    wallet_data = None

    # Ищем по полному адресу
    for addr, shortname, net in wallets:
        if addr.lower() == address.lower():
            wallet_data = (addr, shortname, net)
            break

    # Ищем по короткому формату
    if not wallet_data:
        for addr, shortname, net in wallets:
            short_addr = f"{addr[:6]}...{addr[-4:]}"
            if short_addr.lower() == address.lower():
                wallet_data = (addr, shortname, net)
                break

    if not wallet_data:
        await update.message.reply_text(
            '❌ Адрес не найден в ваших кошельках. Попытайтесь еще раз.',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
        )
        return REMOVE_ADDRESS

    wallet_address, shortname, network = wallet_data

    context.user_data['wallet_address'] = wallet_address
    context.user_data['shortname'] = shortname
    context.user_data['network'] = network

    short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}"
    network_display = network.upper()
    if network == 'bnb':
        network_display = 'BNB Chain'
    elif network == 'eth':
        network_display = 'Ethereum'
    elif network == 'tron':
        network_display = 'TRON'

    await update.message.reply_text(
        f'⚠️ Вы уверены, что хотите удалить кошелек?\n\n'
        f'Адрес: `{short_addr}`\n'
        f'Название: `{shortname}`\n'
        f'Сеть: {network_display}\n\n'
        f'Напишите `УДАЛИТЬ` для подтверждения.',
        reply_markup=ReplyKeyboardMarkup([['УДАЛИТЬ'], ['Отменить']], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return REMOVE_CONFIRM


async def remove_wallet_confirm(update: Update, context: CallbackContext):
    """Подтверждение удаления кошелька."""
    if update.message.text.strip() != 'УДАЛИТЬ':
        await update.message.reply_text(
            '❌ Отклонено. Кошелек не удален.',
            reply_markup=get_main_menu()
        )
        context.user_data.clear()
        return ConversationHandler.END

    db = context.bot_data['db']
    user_id = update.message.from_user.id
    wallet_address = context.user_data['wallet_address']
    shortname = context.user_data['shortname']
    network = context.user_data['network']

    db.remove_wallet(user_id, wallet_address, shortname, network)

    short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}"
    network_display = network.upper()
    if network == 'bnb':
        network_display = 'BNB Chain'
    elif network == 'eth':
        network_display = 'Ethereum'
    elif network == 'tron':
        network_display = 'TRON'

    await update.message.reply_text(
        f'✅ Кошелек удален!\n\n'
        f'📍 `{short_addr}` ({shortname})\n'
        f'🔔 Уведомления для этого кошелька прекращены.',
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )
    context.user_data.clear()
    return ConversationHandler.END


async def handle_buttons(update: Update, context: CallbackContext):
    """Обрабатывает кнопки меню, которые не являются частью диалогов."""
    text = update.message.text
    if text == 'Мои кошельки':
        await list_wallets(update, context)
    elif text == 'Суммы за день':
        await today_incomes_multi_chain(update, context)
    elif text == 'Помощь':
        await help_command(update, context)
    # Другие кнопки обрабатываются ConversationHandler