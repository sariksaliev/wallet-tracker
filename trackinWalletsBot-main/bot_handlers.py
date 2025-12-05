import re
from datetime import datetime, timedelta
import pytz
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from web3 import Web3

from config import ADD_ADDRESS, REMOVE_ADDRESS, REMOVE_CONFIRM, TODAY_WALLET_CHOICE, ADD_SHORTNAME, ADD_NETWORK, \
    TRON_API_KEY, TRON_EXPLORER, TRC20_SYMBOLS, logger
from config import TZ_UTC_PLUS_3, CHAIN_TOKENS, SUPPORTED_CHAINS, EXPLORERS
from etherscan_api import EtherscanAPI, EtherscanAPIError
from trongrid_api import TronGridAPI
from bsc_rpc_api import BscRPC


# --- Допоміжні функції ---

def is_valid_address(address: str) -> bool:
    """Перевіряє валідність адреси."""
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


def get_main_menu() -> ReplyKeyboardMarkup:
    """Повертає головне меню."""
    keyboard = [['Добавить кошелек', 'Удалить кошелек'],
                ['Мои кошельки', 'Суммы за день'],
                ['Помощь']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# --- Основні обробники команд ---

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        'Привет! 👋 Я бот для отслеживания поступлений на кошелек.\n\n'
        '📅 Каждый день в 00:00 (UTC) я отправляю отчет с входящими транзакциями за прошедший день.\n'
        'Выберите действие из меню:',
        reply_markup=get_main_menu()
    )


async def list_wallets(update: Update, context: CallbackContext):
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
    for i, (addr, shortname, _) in enumerate(wallets, 1):
        message += f"{i}. `{addr}` ({shortname})\n"

    message += "\n📊 Отчет поступлений посылается ежедневно в 00:00 (UTC+3)."
    await update.message.reply_text(message, reply_markup=get_main_menu(), parse_mode='Markdown')


async def today_incomes_multi_chain(update: Update, context: CallbackContext):
    db = context.bot_data['db']
    user_id = update.message.from_user.id
    wallets = db.get_wallets(user_id)

    if not wallets:
        await update.message.reply_text(
            'ℹ️ У вас нет добавленных кошельков.',
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    # Формуємо повідомлення зі списком гаманців
    message = '📊 Выберите кошелек для проверки поступлений за сегодня\n\n'
    message += 'Введите полный адрес одного из ваших кошельков:\n\n'
    for addr, shortname, _ in wallets:
        message += f"• `{addr}` ({shortname})\n"

    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return TODAY_WALLET_CHOICE


async def today_wallet_choice(update: Update, context: CallbackContext):
    db = context.bot_data['db']
    user_id = update.message.from_user.id
    selected_address = update.message.text.strip()

    # Перевіряємо, чи введена адреса належить користувачу
    wallets = db.get_wallets(user_id)
    wallet_addresses = [addr.lower() for addr, shortname, _ in wallets]
    if selected_address.lower() not in wallet_addresses:
        await update.message.reply_text(
            '❌ Введенный адрес не относится к вашим кошелькам. Попробуйте снова.',
            reply_markup=ReplyKeyboardMarkup([['Відмінити']], resize_keyboard=True, one_time_keyboard=True)
        )
        return TODAY_WALLET_CHOICE

    # Отримуємо shortname та network
    wallet_data = next(
        (addr, shortname, network) for addr, shortname, network in wallets
        if addr.lower() == selected_address.lower()
    )
    wallet_address, shortname, network = wallet_data

    # Зберігаємо обрану адресу в context.user_data
    context.user_data['selected_wallet'] = selected_address
    context.user_data['network'] = network

    # Обробка транзакцій для обраного гаманця
    now_utc3 = datetime.now(TZ_UTC_PLUS_3)
    today_end = now_utc3.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = today_end - timedelta(days=1)
    ts_start = int(today_start.timestamp())
    ts_end = int(today_end.timestamp())

    await update.message.reply_text(
        f'🔄 Получаю поступление за сегодня для кошелька `{selected_address}` ({shortname})...',
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )

    all_transactions = []
    token_sums = {}  # Словник для підрахунку сум за tokenSymbol

    if network == 'eth':
        for chain_id, chain_name in SUPPORTED_CHAINS.items():
            # ОСОБАЯ ОБРАБОТКА ДЛЯ BNB CHAIN (ID: 56) ЧЕРЕЗ RPC
            if chain_id == 56:  # BNB Chain
                logger.info(f"Обработка BNB Chain через RPC для {selected_address}")

                try:
                    # Получаем BSC RPC клиент из context
                    bsc_rpc = context.bot_data.get('bsc_rpc')
                    if not bsc_rpc:
                        bsc_rpc = BscRPC()
                        context.bot_data['bsc_rpc'] = bsc_rpc

                    # Получаем транзакции через RPC
                    native_txs, token_txs = bsc_rpc.get_historical_transactions(
                        selected_address, ts_start, ts_end
                    )

                    # Обрабатываем нативные транзакции (BNB)
                    for tx in native_txs:
                        if tx.get('is_native') and tx.get('value', 0) > 0:
                            amount = tx['value'] / 1e18  # BNB имеет 18 decimals
                            all_transactions.append({
                                'chain_id': chain_id,
                                'chain_name': chain_name,
                                'wallet': selected_address,
                                'amount': amount,
                                'token': 'BNB',
                                'sender': tx.get('from', ''),
                                'timestamp': tx.get('timestamp', 0),
                                'hash': tx.get('hash', '')
                            })
                            token_sums['BNB'] = token_sums.get('BNB', 0) + amount

                    # Обрабатываем BEP20 токены
                    for tx in token_txs:
                        if not tx.get('is_native') and tx.get('value', 0) > 0:
                            # Получаем decimals токена
                            try:
                                contract_address = tx.get('contract_address', '')
                                token_symbol = tx.get('token_symbol', 'UNKNOWN')

                                # Определяем decimals
                                decimals = 18  # По умолчанию для BEP20
                                if contract_address == '0x55d398326f99059ff775485246999027b3197955':  # USDT
                                    decimals = 18
                                elif contract_address == '0xe9e7cea3dedca5984780bafc599bd69add087d56':  # BUSD
                                    decimals = 18
                                elif contract_address == '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d':  # USDC
                                    decimals = 18

                                amount = tx['value'] / (10 ** decimals)

                                # Фильтруем очень маленькие суммы
                                if amount <= 0.01:
                                    continue

                                all_transactions.append({
                                    'chain_id': chain_id,
                                    'chain_name': chain_name,
                                    'wallet': selected_address,
                                    'amount': amount,
                                    'token': token_symbol,
                                    'sender': tx.get('from', ''),
                                    'timestamp': tx.get('timestamp', 0),
                                    'hash': tx.get('hash', '')
                                })
                                token_sums[token_symbol] = token_sums.get(token_symbol, 0) + amount

                            except Exception as e:
                                logger.error(f"Ошибка обработки BEP20 транзакции: {e}")
                                continue

                    logger.info(f"BNB Chain: обработано {len(native_txs) + len(token_txs)} транзакций")

                except Exception as e:
                    logger.error(f"Ошибка BSC RPC: {e}")
                    # Продолжаем работу, просто пропускаем BNB Chain

            else:
                # Для остальных сетей используем Etherscan
                api = EtherscanAPI(api_key=context.bot_data['api_key'], chain_id=chain_id)

                native_txs = []
                try:
                    result = api.get_chain_transactions(selected_address)
                    if result is not None:
                        native_txs = result
                except EtherscanAPIError as e:
                    logger.warning(f"Пропускаем нативные транзакции в сети {chain_id} после 5 попыток:")
                except Exception as e:
                    logger.error(f"Неизвестная ошибка")

                if native_txs:
                    for tx in native_txs:
                        if (tx.get('to', '').lower() == selected_address.lower() and
                                ts_start <= int(tx.get('timeStamp', 0)) <= ts_end and
                                int(tx.get('value', 0)) > 0):
                            amount = int(tx['value']) / 1e18
                            all_transactions.append({
                                'chain_id': chain_id,
                                'chain_name': chain_name,
                                'wallet': selected_address,
                                'amount': int(tx['value']) / 1e18,
                                'token': CHAIN_TOKENS.get(chain_id, 'UNKNOWN'),
                                'sender': tx.get('from', ''),
                                'timestamp': int(tx['timeStamp']),
                                'hash': tx.get('hash')
                            })
                            token = CHAIN_TOKENS.get(chain_id, 'UNKNOWN')
                            token_sums[token] = token_sums.get(token, 0) + amount

                token_txs = []
                try:
                    result = api.get_token_transactions(selected_address)
                    if result is not None:
                        token_txs = result
                except EtherscanAPIError as e:
                    logger.warning(f"Пропускаем токенные транзакции в сети {chain_id} после 5 попыток:")
                except Exception as e:
                    logger.error(f"Неизвестная ошибка")

                if token_txs:
                    for tx in token_txs:
                        token_symbol = tx.get('tokenSymbol')
                        if (tx.get('to', '').lower() == selected_address.lower() and
                                ts_start <= int(tx.get('timeStamp', 0)) <= ts_end and
                                int(tx.get('value', 0)) > 0):
                            decimals = int(tx.get('tokenDecimal', 18))
                            amount = int(tx['value']) / (10 ** decimals)
                            if amount <= 0.01:
                                continue
                            all_transactions.append({
                                'chain_id': chain_id,
                                'chain_name': chain_name,
                                'wallet': selected_address,
                                'amount': amount,
                                'token': token_symbol,
                                'sender': tx.get('from', ''),
                                'timestamp': int(tx['timeStamp']),
                                'hash': tx.get('hash')
                            })
                            token_sums[token_symbol] = token_sums.get(token_symbol, 0) + amount

    elif network == 'tron':
        api = TronGridAPI(api_key=context.bot_data.get('tron_api_key', TRON_API_KEY))
        native_txs = api.get_chain_transactions(selected_address)
        for tx in native_txs:
            ts_ms = tx.get('raw_data', {}).get('timestamp', 0)
            ts = ts_ms // 1000

            # Перевірка типу контракту
            contract = tx.get('raw_data', {}).get('contract', [])
            if not contract:
                continue

            contract_type = contract[0].get('type')
            value = contract[0].get('parameter', {}).get('value', {})

            # Нативна TRX транзакція
            if contract_type == 'TransferContract':
                to_address = value.get('to_address', '').lower()
                if (to_address == selected_address.lower() and
                        ts_start <= ts <= ts_end and
                        value.get('amount', 0) > 0):
                    amount_trx = int(value['amount']) / 1e6
                    sender_address = value.get('owner_address', '')
                    all_transactions.append({
                        'chain_id': 'tron',
                        'chain_name': 'TRON',
                        'wallet': selected_address,
                        'amount': amount_trx,
                        'token': 'TRX',
                        'sender': f"{sender_address[:6]}...{sender_address[-4:]}",
                        'timestamp': ts,
                        'hash': tx.get('txID'),
                    })
                    token_sums['TRX'] = token_sums.get('TRX', 0) + amount_trx

            # Токенова TRC-20 транзакція
            elif contract_type == 'TriggerSmartContract':
                data_hex = value.get('data', '')

                # Парсимо отримувача і суму
                amount_hex = data_hex[72:136]
                amount = int(amount_hex, 16)

                if (ts_start <= ts <= ts_end and
                        amount > 0):
                    amount_token = amount / 1e6
                    sender_address = value.get('owner_address', '')
                    token_contract = value.get('contract_address', '').lower()
                    token_symbol = TRC20_SYMBOLS.get(token_contract)
                    all_transactions.append({
                        'chain_id': 'tron',
                        'chain_name': 'TRON',
                        'wallet': selected_address,
                        'amount': amount_token,
                        'token': token_symbol,
                        'sender': f"{sender_address}",
                        'timestamp': ts,
                        'hash': tx.get('txID'),
                    })
                    token_sums[token_symbol] = token_sums.get(token_symbol, 0) + amount_token

        trc20_transfers = api.get_trc20_transfers(selected_address)
        for transfer in trc20_transfers:
            timestamp = transfer['block_timestamp'] // 1000

            if not (ts_start <= timestamp <= ts_end):
                continue

            to_addr = transfer.get('to', '').lower()
            if to_addr != selected_address.lower():
                continue  # тільки вхідні на наш гаманець

            token_info = transfer['token_info']
            symbol = token_info['symbol']
            decimals = int(token_info.get('decimals', 6))
            amount_raw = int(transfer['value'])
            amount = amount_raw / (10 ** decimals)

            if amount <= 0:
                continue

            sender = transfer.get('from', '')

            all_transactions.append({
                'chain_id': 'tron',
                'chain_name': 'TRON',
                'wallet': selected_address,
                'amount': amount,
                'token': symbol,
                'sender': f"{sender[:8]}...{sender[-6:]}",
                'timestamp': timestamp,
                'hash': transfer['transaction_id'],
            })
            token_sums[symbol] = token_sums.get(symbol, 0) + amount

    if not all_transactions:
        await update.message.reply_text(
            "💸 Сегодня не было поступлений для этого кошелька.",
            reply_markup=get_main_menu()
        )
        context.user_data.clear()
        return ConversationHandler.END

    all_transactions.sort(key=lambda x: x['timestamp'])
    chunks = [all_transactions[i:i + 10] for i in range(0, len(all_transactions), 20)]

    for chunk in chunks:
        msg = f"📊 Поступление с 00:00 до {today_start.strftime('%Y-%m-%d')} (UTC+3)\n\n"
        for tx in chunk:
            short_wallet = f"{tx['wallet'][:6]}...{tx['wallet'][-4:]}"
            short_sender = f"{tx['sender']}"
            tx_time = datetime.fromtimestamp(tx['timestamp'], TZ_UTC_PLUS_3).strftime('%H:%M:%S')
            explorer_template = (
                TRON_EXPLORER
                if tx['chain_id'] == 'tron'
                else EXPLORERS.get(tx['chain_id'], "https://etherscan.io/tx/{}")
            )
            explorer_url = explorer_template.format(tx['hash'])
            msg += (f"• `{short_wallet}` ({tx['chain_name']}): {tx['amount']:.6f} {tx['token']}\n"
                    f"  От: `{short_sender}`\n"
                    f"  Время: {tx_time}\n"
                    f"  🔗 [Транзакция]({explorer_url})\n\n")

        msg += f"🕒 Обновлено: {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S UTC+3')}"
        await update.message.reply_text(
            msg,
            reply_markup=get_main_menu(),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    if token_sums:
        sums_msg = f"💰 Итоговая сумма поступлений с 00:00 до {now_utc3.strftime('%H:%M:%S')} ({today_start.strftime('%Y-%m-%d')}) для кошелька `{selected_address}` ({shortname}) (UTC+3)\n\n"
        for token, total in token_sums.items():
            sums_msg += f"• {token}: {total:.3f}\n"
        sums_msg += f"\n🕒 Обновлено: {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S UTC+3')}"
        await update.message.reply_text(
            sums_msg,
            reply_markup=get_main_menu(),
            parse_mode='Markdown'
        )

    context.user_data.clear()
    return ConversationHandler.END


async def process_today_incomes_job(context):
    db = context.bot_data['db']
    api_key = context.bot_data['api_key']

    users = db.get_all_users()
    if not users:
        return

    now_utc3 = datetime.now(TZ_UTC_PLUS_3)
    today_end = now_utc3.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = today_end - timedelta(days=1)
    ts_start = int(today_start.timestamp())
    ts_end = int(today_end.timestamp())

    for user_id in users:
        # Отримуємо гаманці користувача
        wallets = db.get_wallets(user_id)
        if not wallets:
            await context.bot.send_message(
                chat_id=user_id,
                text="ℹ️ У вас нет добавленных кошельков.",
                reply_markup=get_main_menu()
            )
            continue

        # Виводимо список гаманців
        wallets_msg = f"📋 Ваши добавленные кошельки ({today_start.strftime('%Y-%m-%d')}):\n\n"
        for wallet_address, shortname, network in wallets:
            short_wallet = f"{wallet_address[:6]}...{wallet_address[-4:]}"
            wallets_msg += f"• `{short_wallet}` ({shortname})\n"
        wallets_msg += f"\n🕒 Обновлено: {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S UTC+3')}"
        await context.bot.send_message(
            chat_id=user_id,
            text=wallets_msg,
            reply_markup=get_main_menu(),
            parse_mode='Markdown'
        )

        # Обробка транзакцій для кожного гаманця окремо
        for wallet_address, shortname, network in wallets:
            short_wallet = f"{wallet_address[:6]}...{wallet_address[-4:]}"
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔄 Получаю поступление за сегодня для кошелька `{short_wallet}` ({shortname})...",
                reply_markup=get_main_menu(),
                parse_mode='Markdown'
            )

            wallet_transactions = []
            token_sums = {}

            if network == 'eth':
                for chain_id, chain_name in SUPPORTED_CHAINS.items():
                    # ОСОБАЯ ОБРАБОТКА ДЛЯ BNB CHAIN (ID: 56) ЧЕРЕЗ RPC
                    if chain_id == 56:  # BNB Chain
                        logger.info(f"Обработка BNB Chain через RPC для {wallet_address}")

                        try:
                            # Получаем BSC RPC клиент из context
                            bsc_rpc = context.bot_data.get('bsc_rpc')
                            if not bsc_rpc:
                                bsc_rpc = BscRPC()
                                context.bot_data['bsc_rpc'] = bsc_rpc

                            # Получаем транзакции через RPC
                            native_txs, token_txs = bsc_rpc.get_historical_transactions(
                                wallet_address, ts_start, ts_end
                            )

                            # Обрабатываем нативные транзакции (BNB)
                            for tx in native_txs:
                                if tx.get('is_native') and tx.get('value', 0) > 0:
                                    amount = tx['value'] / 1e18  # BNB имеет 18 decimals
                                    wallet_transactions.append({
                                        'chain_id': chain_id,
                                        'chain_name': chain_name,
                                        'wallet': wallet_address,
                                        'amount': amount,
                                        'token': 'BNB',
                                        'sender': tx.get('from', ''),
                                        'timestamp': tx.get('timestamp', 0),
                                        'hash': tx.get('hash', '')
                                    })
                                    token_sums['BNB'] = token_sums.get('BNB', 0) + amount

                            # Обрабатываем BEP20 токены
                            for tx in token_txs:
                                if not tx.get('is_native') and tx.get('value', 0) > 0:
                                    # Получаем decimals токена
                                    try:
                                        contract_address = tx.get('contract_address', '')
                                        token_symbol = tx.get('token_symbol', 'UNKNOWN')

                                        # Определяем decimals
                                        decimals = 18  # По умолчанию для BEP20
                                        if contract_address == '0x55d398326f99059ff775485246999027b3197955':  # USDT
                                            decimals = 18
                                        elif contract_address == '0xe9e7cea3dedca5984780bafc599bd69add087d56':  # BUSD
                                            decimals = 18
                                        elif contract_address == '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d':  # USDC
                                            decimals = 18

                                        amount = tx['value'] / (10 ** decimals)

                                        # Фильтруем очень маленькие суммы
                                        if amount <= 0.01:
                                            continue

                                        wallet_transactions.append({
                                            'chain_id': chain_id,
                                            'chain_name': chain_name,
                                            'wallet': wallet_address,
                                            'amount': amount,
                                            'token': token_symbol,
                                            'sender': tx.get('from', ''),
                                            'timestamp': tx.get('timestamp', 0),
                                            'hash': tx.get('hash', '')
                                        })
                                        token_sums[token_symbol] = token_sums.get(token_symbol, 0) + amount

                                    except Exception as e:
                                        logger.error(f"Ошибка обработки BEP20 транзакции: {e}")
                                        continue

                            logger.info(f"BNB Chain: обработано {len(native_txs) + len(token_txs)} транзакций")

                        except Exception as e:
                            logger.error(f"Ошибка BSC RPC: {e}")
                            # Продолжаем работу, просто пропускаем BNB Chain

                    else:
                        # Для остальных сетей используем Etherscan
                        api = EtherscanAPI(api_key=api_key, chain_id=chain_id)
                        native_txs = []
                        try:
                            result = api.get_chain_transactions(wallet_address)
                            if result is not None:
                                native_txs = result
                        except EtherscanAPIError as e:
                            logger.warning(f"Пропускаем нативные транзакции в сети {chain_id} после 5 попыток:")
                        except Exception as e:
                            logger.error(f"Неизвестная ошибка")

                        if native_txs:
                            for tx in native_txs:
                                if (tx.get('to', '').lower() == wallet_address.lower() and
                                        ts_start <= int(tx.get('timeStamp', 0)) <= ts_end and
                                        int(tx.get('value', 0)) > 0):
                                    amount = int(tx['value']) / 1e18
                                    wallet_transactions.append({
                                        'chain_id': chain_id,
                                        'chain_name': chain_name,
                                        'wallet': wallet_address,
                                        'amount': amount,
                                        'token': CHAIN_TOKENS.get(chain_id, 'UNKNOWN'),
                                        'sender': tx.get('from', ''),
                                        'timestamp': int(tx['timeStamp']),
                                        'hash': tx.get('hash')
                                    })
                                    token = CHAIN_TOKENS.get(chain_id, 'UNKNOWN')
                                    token_sums[token] = token_sums.get(token, 0) + amount

                        token_txs = []
                        try:
                            result = api.get_token_transactions(wallet_address)
                            if result is not None:
                                token_txs = result
                        except EtherscanAPIError as e:
                            logger.warning(f"Пропускаем токенные транзакции в сети {chain_id} после 5 попыток:")
                        except Exception as e:
                            logger.error(f"Неизвестная ошибка")

                        if token_txs:
                            for tx in token_txs:
                                token_symbol = tx.get('tokenSymbol')
                                if (tx.get('to', '').lower() == wallet_address.lower() and
                                        ts_start <= int(tx.get('timeStamp', 0)) <= ts_end and
                                        int(tx.get('value', 0)) > 0):
                                    decimals = int(tx.get('tokenDecimal', 18))
                                    amount = int(tx['value']) / (10 ** decimals)
                                    if amount <= 0.01:
                                        continue
                                    wallet_transactions.append({
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

            elif network == 'tron':
                api = TronGridAPI(api_key=context.bot_data.get('tron_api_key', TRON_API_KEY))
                native_txs = api.get_chain_transactions(wallet_address)

                for tx in native_txs:
                    ts_ms = tx.get('raw_data', {}).get('timestamp', 0)
                    ts = ts_ms // 1000

                    contract = tx.get('raw_data', {}).get('contract', [])
                    if not contract:
                        continue

                    contract_type = contract[0].get('type')
                    value = contract[0].get('parameter', {}).get('value', {})

                    # Нативна TRX транзакція
                    if contract_type == 'TransferContract':
                        to_address = value.get('to_address', '').lower()
                        if to_address == wallet_address.lower() and ts_start <= ts <= ts_end and value.get('amount',
                                                                                                           0) > 0:
                            amount_trx = int(value['amount']) / 1e6
                            sender_address = value.get('owner_address', '')
                            wallet_transactions.append({
                                'chain_id': 'tron',
                                'chain_name': 'TRON',
                                'wallet': wallet_address,
                                'amount': amount_trx,
                                'token': 'TRX',
                                'sender': f"{sender_address[:6]}...{sender_address[-4:]}",
                                'timestamp': ts_ms,
                                'hash': tx.get('txID')
                            })
                            token_sums['TRX'] = token_sums.get('TRX', 0) + amount_trx

                    # Токенова TRC-20 транзакція
                    elif contract_type == 'TriggerSmartContract':
                        data_hex = value.get('data', '')
                        amount_hex = data_hex[72:136]
                        amount = int(amount_hex, 16)

                        if ts_start <= ts_ms <= ts_end and amount > 0:
                            amount_token = amount / 1e6
                            sender_address = value.get('owner_address', '')
                            contract_address = value.get('contract_address', '').lower()
                            token_symbol = TRC20_SYMBOLS.get(contract_address,
                                                             contract_address[:6] + '...' + contract_address[-4:])
                            wallet_transactions.append({
                                'chain_id': 'tron',
                                'chain_name': 'TRON',
                                'wallet': wallet_address,
                                'amount': amount_token,
                                'token': token_symbol,
                                'sender': f"{sender_address[:6]}...{sender_address[-4:]}",
                                'timestamp': ts,
                                'hash': tx.get('txID')
                            })
                            token_sums[token_symbol] = token_sums.get(token_symbol, 0) + amount_token

                trc20_transfers = api.get_trc20_transfers(wallet_address)
                for transfer in trc20_transfers:
                    timestamp = transfer['block_timestamp'] // 1000

                    if not (ts_start <= timestamp <= ts_end):
                        continue

                    to_addr = transfer.get('to', '').lower()
                    if to_addr != wallet_address.lower():
                        continue

                    token_info = transfer['token_info']
                    symbol = token_info['symbol']
                    decimals = int(token_info.get('decimals', 6))
                    amount_raw = int(transfer['value'])
                    amount = amount_raw / (10 ** decimals)

                    if amount <= 0:
                        continue

                    sender = transfer.get('from', '')
                    wallet_transactions.append({
                        'chain_id': 'tron',
                        'chain_name': 'TRON',
                        'wallet': wallet_address,
                        'amount': amount,
                        'token': symbol,
                        'sender': f"{sender[:8]}...{sender[-6:]}",
                        'timestamp': timestamp,
                        'hash': transfer['transaction_id'],
                    })
                    token_sums[symbol] = token_sums.get(symbol, 0) + amount

            # Виводимо транзакції для поточного гаманця
            if not wallet_transactions:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"💸 Сегодня не было поступлений для кошелька `{short_wallet}` ({shortname}).",
                    reply_markup=get_main_menu(),
                    parse_mode='Markdown'
                )
                continue

            wallet_transactions.sort(key=lambda x: x['timestamp'])
            chunks = [wallet_transactions[i:i + 20] for i in range(0, len(wallet_transactions), 20)]

            for chunk in chunks:
                msg = f"📊 Поступление за {today_start.strftime('%Y-%m-%d')} для кошелька `{short_wallet}` ({shortname}) (UTC+3)\n\n"
                for tx in chunk:
                    tx_time = datetime.fromtimestamp(tx['timestamp'], TZ_UTC_PLUS_3).strftime('%H:%M:%S')
                    explorer_template = EXPLORERS.get(tx['chain_id'], "https://etherscan.io/tx/{}")
                    explorer_url = explorer_template.format(tx['hash'])
                    msg += (f"• `{short_wallet}` ({tx['chain_name']}): {tx['amount']:.3f} {tx['token']}\n"
                            f"  От: `{tx['sender']}`\n"
                            f"  Время: {tx_time}\n"
                            f"  🔗 [Транзакция]({explorer_url})\n\n")

                msg += f"🕒 Обновлено: {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S UTC+3')}"
                await context.bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    reply_markup=get_main_menu(),
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )

            if token_sums:
                summary_msg = f"💰 Итоговая сумма поступлений за прошедший день для кошелька `{short_wallet}` ({shortname}) (UTC+3):\n\n"
                for token, total in sorted(token_sums.items(), key=lambda x: x[1], reverse=True):
                    summary_msg += f"• {token}: {total:.3f}\n"
                summary_msg += f"\n🕒 Обновлено: {datetime.now(TZ_UTC_PLUS_3).strftime('%H:%M:%S UTC+3')}"
                await context.bot.send_message(
                    chat_id=user_id,
                    text=summary_msg,
                    reply_markup=get_main_menu(),
                    parse_mode='Markdown'
                )


async def help_command(update: Update, context: CallbackContext):
    help_text = """
🔧 Как пользоваться ботом:

1️⃣ Добавить кошелек: 
• Нажмите "Добавить кошелек" 
• Выберите сеть. 
• Введите адрес. 
• Введите название кошелька.

2️⃣ Удалить кошелек: 
• Нажмите "Удалить кошелек" 
• Введите адрес для удаления. 
• Подтвердите удаление.

3️⃣ Суммы за день: 
• Нажмите "Суммы за день".

4️⃣ Отчет: 
• Ежедневно в 00:00 (UTC+3) посылается отчет за прошедший день. 
"""
    await update.message.reply_text(help_text, reply_markup=get_main_menu(), parse_mode='Markdown')


def is_valid_tron_address(address: str) -> bool:
    """Перевіряє валідність TRON-адреси (Base58 або hex)."""
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
    keyboard = [['ETH', 'TRON'], ['Відмінити']]
    await update.message.reply_text(
        '➕ Добавление кошелька\n\n'
        'Выберите сеть:',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return ADD_NETWORK


async def add_wallet_network(update: Update, context: CallbackContext):
    network_choice = update.message.text.strip().lower()
    if network_choice == 'eth':
        context.user_data['pending_network'] = 'eth'
        await update.message.reply_text(
            '📥 Введите адрес ETH-кошелька (начинается с 0x):',
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
            '❌ Некоректный выбор сети. Выберите ETH или TRON.',
            reply_markup=ReplyKeyboardMarkup([['ETH', 'TRON'], ['Отменить']], resize_keyboard=True,
                                             one_time_keyboard=True)
        )
        return ADD_NETWORK


async def add_wallet_address(update: Update, context: CallbackContext):
    wallet_address = update.message.text.strip()
    user_id = update.message.from_user.id
    db = context.bot_data['db']
    network = context.user_data.get('pending_network', 'eth')

    # Перевірка валідності адреси
    if network == 'eth':
        if not Web3.is_address(wallet_address):
            await update.message.reply_text(
                '❌ Недействительный адрес ETH!\n\n'
                'Адрес должен:\n'
                '• Начинаться с `0x`\n'
                '• Содержит 42 символа\n'
                '• Состоять из символов (0-9, a-f)',
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
            )
            return ADD_ADDRESS
    elif network == 'tron':
        if not is_valid_tron_address(wallet_address):
            await update.message.reply_text(
                '❌ Недействительный адрес TRON!\n\n'
                'Адрес должен:\n'
                '• Начинаться с `T` (Base58, 34 символа) или `41` (hex, 42 символа)',
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
            )
            return ADD_ADDRESS

    # Перевірка, чи адреса вже додана
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
        f'📝 Введите короткое название для кошелька {network.upper()}. '
        'Название должно быть уникальным:',
        reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return ADD_SHORTNAME


async def add_wallet_shortname(update: Update, context: CallbackContext):
    shortname = update.message.text.strip()
    user_id = update.message.from_user.id
    wallet_address = context.user_data.get('pending_wallet_address')
    network = context.user_data.get('pending_network', 'eth')  # ← отримуємо мережу
    db = context.bot_data['db']

    if not wallet_address:
        await update.message.reply_text(
            'Ошибка: адрес кошелька не найден. Начните добавление заново.',
            reply_markup=get_main_menu()
        )
        context.user_data.clear()
        return ConversationHandler.END

    if len(shortname) > 20 or len(shortname) < 1:
        await update.message.reply_text(
            'Короткое название должно быть от 1 до 20 символов. Попробуйте еще раз:',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
            parse_mode='Markdown'
        )
        return ADD_SHORTNAME

    if not re.fullmatch(r'[a-zA-Z0-9 ]+', shortname):
        await update.message.reply_text(
            'Короткое название может содержать только латинские буквы (a-z, A-Z), цифры (0-9) и пробелы.\n'
            'Попробуйте еще раз:',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
            parse_mode='Markdown'
        )
        return ADD_SHORTNAME

    if db.add_wallet(user_id, wallet_address, shortname, network):
        short_wallet = f"{wallet_address[:6]}...{wallet_address[-4:]}"
        await update.message.reply_text(
            f'Кошелек `{short_wallet}` ({shortname}) в сети {network.upper()} успешно добавлен!',
            reply_markup=get_main_menu(),
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            f'Кошелек с адресом `{wallet_address[:6]}...{wallet_address[-4:]}` или название `{shortname}` '
            f'в сети {network.upper()} уже используется! Попробуйте другое название.',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
            parse_mode='Markdown'
        )
        return ADD_SHORTNAME


async def remove_wallet_start(update: Update, context: CallbackContext):
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
    message += 'Введите полный адрес одного из ваших кошельков:\n\n'
    for addr, shortname, _ in wallets:
        message += f"• `{addr}` ({shortname})\n"  # Виводимо повну адресу

    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return REMOVE_ADDRESS


async def remove_wallet_address(update: Update, context: CallbackContext):
    address = update.message.text.strip()
    user_id = update.message.from_user.id
    db = context.bot_data['db']

    wallets = db.get_wallets(user_id)
    wallet_data = next(
        ((addr, shortname, net) for addr, shortname, net in wallets if addr.lower() == address.lower()),
        None
    )

    if not wallet_data:
        await update.message.reply_text(
            'Адрес не найден в ваших кошельках. Попытайтесь еще раз.',
            reply_markup=ReplyKeyboardMarkup([['Отменить']], resize_keyboard=True, one_time_keyboard=True)
        )
        return REMOVE_ADDRESS

    wallet_address, shortname, network = wallet_data

    context.user_data['wallet_address'] = wallet_address
    context.user_data['shortname'] = shortname
    context.user_data['network'] = network

    short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}"
    await update.message.reply_text(
        f'Вы уверены, что хотите удалить кошелек?\n\n'
        f'Адрес: `{short_addr}`\n'
        f'Название: `{shortname}`\n'
        f'Сеть: {network.upper()}\n\n'
        f'Напишите `УДАЛИТЬ` для подтверждения.',
        reply_markup=ReplyKeyboardMarkup([['УДАЛИТЬ'], ['Отменить']], resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return REMOVE_CONFIRM


async def remove_wallet_confirm(update: Update, context: CallbackContext):
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
    await update.message.reply_text(
        f'✅ Кошелек удален!\n\n'
        f'📍 `{short_addr}` ({shortname})\n'
        f'🔔 Уведомление об этом кошельке прекращено.',
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )
    context.user_data.clear()
    return ConversationHandler.END


async def handle_buttons(update: Update, context: CallbackContext):
    """Обробляє кнопки меню, які не є частиною діалогів."""
    text = update.message.text
    if text == 'Мои кошельки':
        await list_wallets(update, context)
    elif text == 'Суммы за день':
        await today_incomes_multi_chain(update, context)
    elif text == 'Помощь':
        await help_command(update, context)
    # Інші кнопки обробляються ConversationHandler