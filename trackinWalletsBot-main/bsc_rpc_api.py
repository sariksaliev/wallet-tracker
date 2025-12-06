import requests
import time
from typing import List, Dict, Optional, Tuple
from web3 import Web3
from config import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from web3.exceptions import BlockNotFound, TransactionNotFound


class BscRPCError(Exception):
    pass


class BscRPC:
    """RPC клиент для BNB Smart Chain"""

    # Список публичных RPC узлов BSC (добавил более стабильные)
    RPC_ENDPOINTS = [
        "https://rpc.ankr.com/bsc",  # Более стабильный
        "https://bsc-dataseed1.binance.org",
        "https://bsc-dataseed2.binance.org",
        "https://bsc-dataseed3.binance.org",
        "https://bsc-dataseed4.binance.org",
        "https://bsc-dataseed1.defibit.io",
        "https://bsc-dataseed2.defibit.io",
        "https://1rpc.io/bnb",  # Добавил новый RPC
        "https://bsc.publicnode.com",  # Еще один RPC
        "https://bsc.meowrpc.com",  # Альтернативный RPC
        "https://bsc-dataseed.binance.org/",  # Основной RPC
        "https://bscrpc.com",  # Дополнительный RPC
    ]

    # ERC20 ABI для парсинга токенов (упрощенный)
    ERC20_ABI = [
        {
            "constant": True,
            "inputs": [],
            "name": "name",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "from", "type": "address"},
                {"indexed": True, "name": "to", "type": "address"},
                {"indexed": False, "name": "value", "type": "uint256"}
            ],
            "name": "Transfer",
            "type": "event"
        }
    ]

    # Популярные BEP20 токены BSC
    BEP20_TOKENS = {
        "0x55d398326f99059ff775485246999027b3197955": "USDT",
        "0xe9e7cea3dedca5984780bafc599bd69add087d56": "BUSD",
        "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": "USDC",
        "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB",
        "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82": "CAKE",
        "0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c": "BTCB",
        "0x2170ed0880ac9a755fd29b2688956bd959f933f8": "ETH",
        "0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3": "DAI",
        "0xba2ae424d960c26247dd6c32edc70b295c744c43": "DOGE",
        "0x7083609fce4d1d8dc0c979aab8c869ea2c873402": "DOT",
    }

    def __init__(self):
        self.web3 = None
        self.current_endpoint = 0
        self._connect()

    def _connect(self):
        """Подключается к доступному RPC узлу"""
        max_retries = 5
        for attempt in range(max_retries):
            for i in range(len(self.RPC_ENDPOINTS)):
                endpoint = self.RPC_ENDPOINTS[(self.current_endpoint + i) % len(self.RPC_ENDPOINTS)]
                try:
                    logger.info(f"Попытка подключения к {endpoint} (попытка {attempt + 1}/{max_retries})")

                    self.web3 = Web3(Web3.HTTPProvider(
                        endpoint,
                        request_kwargs={
                            'timeout': 30,
                            'proxies': {'https': '', 'http': ''}  # Отключаем прокси если есть
                        }
                    ))

                    # Проверяем подключение
                    if self.web3.is_connected():
                        # Тестовый запрос для проверки работы
                        block_number = self.web3.eth.get_block_number()
                        block = self.web3.eth.get_block('latest')

                        if block and block.number:
                            logger.info(f"✅ Подключено к BSC RPC: {endpoint} (блок #{block.number})")
                            self.current_endpoint = (self.current_endpoint + i) % len(self.RPC_ENDPOINTS)
                            return True

                except Exception as e:
                    logger.warning(f"Не удалось подключиться к {endpoint}: {e}")
                    continue

            # Если не удалось подключиться ни к одному endpoint, ждем перед повторной попыткой
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Экспоненциальная задержка
                logger.warning(f"Все RPC не отвечают, ждем {wait_time} сек...")
                time.sleep(wait_time)

        raise BscRPCError("Не удалось подключиться ни к одному RPC узлу BSC")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, BscRPCError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Повтор BSC RPC запроса (попытка {retry_state.attempt_number}/5)"
        )
    )
    def _make_rpc_call(self, method: str, params: list = None) -> dict:
        """Выполняет RPC вызов"""
        if params is None:
            params = []

        endpoint = self.RPC_ENDPOINTS[self.current_endpoint]

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }

        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=60  # Увеличил таймаут для тяжелых запросов
            )

            if response.status_code != 200:
                logger.warning(f"HTTP ошибка {response.status_code} от {endpoint}")
                raise BscRPCError(f"HTTP ошибка {response.status_code}")

            data = response.json()

            if 'error' in data:
                error_msg = data['error'].get('message', 'Unknown error')
                # Пропускаем некоторые не критичные ошибки
                if 'filter not found' in error_msg.lower() or 'query returned more than' in error_msg.lower():
                    logger.debug(f"Некритичная RPC ошибка: {error_msg}")
                    return []
                raise BscRPCError(f"RPC ошибка: {error_msg}")

            return data.get('result')

        except requests.exceptions.Timeout:
            logger.warning(f"Таймаут запроса к {endpoint}")
            # Пробуем другой endpoint при таймауте
            self.current_endpoint = (self.current_endpoint + 1) % len(self.RPC_ENDPOINTS)
            self._connect()
            raise
        except Exception as e:
            logger.error(f"Ошибка RPC вызова к {endpoint}: {e}")
            # Пробуем другой endpoint при ошибке
            self.current_endpoint = (self.current_endpoint + 1) % len(self.RPC_ENDPOINTS)
            self._connect()
            raise

    def get_block_by_timestamp(self, timestamp: int) -> int:
        """Получает номер блока по timestamp (приблизительно)"""
        try:
            # Получаем текущий блок
            latest_block = self.web3.eth.get_block('latest')
            latest_timestamp = latest_block.timestamp
            latest_number = latest_block.number

            if timestamp > latest_timestamp:
                return latest_number

            # Для BSC среднее время блока ~3 секунды
            avg_block_time = 3
            blocks_diff = int((latest_timestamp - timestamp) / avg_block_time)
            target_block = max(1, latest_number - blocks_diff)

            # Ограничиваем поиск последними 10000 блоками
            target_block = max(1, target_block)

            logger.info(f"Поиск блока для timestamp {timestamp}: примерный блок {target_block}")
            return target_block

        except Exception as e:
            logger.warning(f"Ошибка получения блока по timestamp: {e}, используем аппроксимацию")
            # Возвращаем приблизительное значение
            current_block = self.web3.eth.get_block_number()
            estimated_block = max(1, current_block - int((time.time() - timestamp) / 3))
            logger.info(f"Используем приблизительный блок: {estimated_block}")
            return estimated_block

    def parse_native_bnb_transactions(self, address: str, start_block: int, end_block: int) -> List[Dict]:
        """Основной метод для парсинга нативных BNB транзакций"""
        transactions = []
        address_lower = address.lower()

        logger.info(f"BSC: Парсинг нативных BNB с {start_block} по {end_block} для {address[:10]}...")

        # Ограничиваем диапазон блоков для производительности
        MAX_BLOCKS_TO_SCAN = 10000
        block_range = end_block - start_block

        if block_range > MAX_BLOCKS_TO_SCAN:
            logger.warning(f"Слишком большой диапазон блоков ({block_range}), ограничиваем до {MAX_BLOCKS_TO_SCAN}")
            start_block = max(start_block, end_block - MAX_BLOCKS_TO_SCAN)
            logger.info(f"Новый диапазон: {start_block} - {end_block}")

        try:
            # МЕТОД 1: Поиск через eth_getLogs с фильтром по адресу получателя
            logger.info("Пробуем метод 1: eth_getLogs с фильтром по получателю...")

            # Формируем hex адрес для фильтра (64 символа, заполненные нулями слева)
            address_hex = "0x" + address[2:].rjust(64, '0')

            logs = self._make_rpc_call("eth_getLogs", [{
                "fromBlock": hex(start_block),
                "toBlock": hex(end_block),
                "topics": [
                    None,  # Любая сигнатура события
                    None,  # Любой отправитель (from)
                    address_hex  # Конкретный получатель (to)
                ]
            }])

            if logs:
                logger.info(f"Найдено {len(logs)} потенциальных транзакций через eth_getLogs")

                processed_hashes = set()
                for i, log in enumerate(logs):
                    try:
                        tx_hash = log.get('transactionHash')
                        if not tx_hash or tx_hash in processed_hashes:
                            continue

                        processed_hashes.add(tx_hash)

                        # Получаем детали транзакции
                        tx = self.web3.eth.get_transaction(tx_hash)
                        if not tx:
                            continue

                        # Проверяем, что это входящая нативная транзакция BNB
                        if (tx.to and
                                tx.to.lower() == address_lower and
                                tx.value and
                                int(tx.value) > 0):

                            # Получаем блок для timestamp
                            try:
                                block = self.web3.eth.get_block(tx.blockNumber)
                                timestamp = block.timestamp if block else int(time.time())
                            except:
                                timestamp = int(time.time())

                            transactions.append({
                                'hash': tx_hash.hex(),
                                'from': tx['from'],
                                'to': tx['to'],
                                'value': tx['value'],
                                'value_eth': self.web3.from_wei(tx.value, 'ether'),
                                'timestamp': timestamp,
                                'is_native': True,
                                'token': 'BNB',
                                'block_number': tx.blockNumber,
                                'gas_price': tx.gasPrice,
                                'gas': tx.gas,
                                'method': 'eth_getLogs'
                            })

                            if len(transactions) % 10 == 0:
                                logger.debug(f"Обработано {len(transactions)} транзакций")

                    except Exception as e:
                        logger.debug(f"Ошибка обработки лога {i}: {e}")
                        continue

            # МЕТОД 2: Если первый метод не нашел транзакций, пробуем парсинг блоков
            if not transactions and block_range <= 500:
                logger.info("Пробуем метод 2: прямой парсинг блоков...")
                transactions = self._parse_blocks_directly(address, start_block, end_block)

            # МЕТОД 3: Альтернативный метод через trace_filter (если поддерживается)
            if not transactions:
                logger.info("Пробуем метод 3: eth_getLogs с другими параметрами...")
                alternative_txs = self._parse_bnb_alternative(address, start_block, end_block)
                if alternative_txs:
                    transactions.extend(alternative_txs)

            # Удаляем дубликаты
            unique_transactions = []
            seen_hashes = set()
            for tx in transactions:
                if tx['hash'] not in seen_hashes:
                    seen_hashes.add(tx['hash'])
                    unique_transactions.append(tx)

            logger.info(f"BSC: Найдено {len(unique_transactions)} уникальных нативных BNB транзакций")
            return unique_transactions

        except Exception as e:
            logger.error(f"Ошибка парсинга BNB транзакций: {e}")
            return []

    def _parse_blocks_directly(self, address: str, start_block: int, end_block: int) -> List[Dict]:
        """Прямой парсинг блоков (для небольших диапазонов)"""
        transactions = []
        address_lower = address.lower()

        # Ограничиваем количество блоков для парсинга
        max_blocks = 100
        blocks_to_scan = min(end_block - start_block + 1, max_blocks)

        logger.info(f"Прямой парсинг {blocks_to_scan} блоков...")

        for i in range(blocks_to_scan):
            block_num = start_block + i
            try:
                # Получаем блок с транзакциями
                block = self.web3.eth.get_block(block_num, full_transactions=True)

                for tx in block.transactions:
                    # Проверяем, что это входящая транзакция с ненулевым значением
                    if (tx.to and
                            tx.to.lower() == address_lower and
                            tx.value and
                            int(tx.value) > 0):
                        transactions.append({
                            'hash': tx.hash.hex(),
                            'from': tx['from'],
                            'to': tx['to'],
                            'value': tx['value'],
                            'value_eth': self.web3.from_wei(tx.value, 'ether'),
                            'timestamp': block.timestamp,
                            'is_native': True,
                            'token': 'BNB',
                            'block_number': block_num,
                            'gas_price': tx.gasPrice,
                            'gas': tx.gas,
                            'method': 'direct_block_parsing'
                        })

                # Логируем прогресс
                if (i + 1) % 10 == 0:
                    logger.info(f"Пропарсено {i + 1}/{blocks_to_scan} блоков, найдено {len(transactions)} транзакций")

            except Exception as e:
                logger.debug(f"Ошибка парсинга блока {block_num}: {e}")
                continue

        logger.info(f"Прямой парсинг завершен, найдено {len(transactions)} транзакций")
        return transactions

    def _parse_bnb_alternative(self, address: str, start_block: int, end_block: int) -> List[Dict]:
        """Альтернативный метод парсинга BNB транзакций"""
        transactions = []
        address_lower = address.lower()

        try:
            logger.info("Альтернативный метод: ищем все логи без фильтра по адресу...")

            # Получаем логи без фильтра по адресу получателя
            logs = self._make_rpc_call("eth_getLogs", [{
                "fromBlock": hex(start_block),
                "toBlock": hex(end_block),
                "address": None,
                "topics": [None]  # Любые события
            }])

            if logs:
                logger.info(f"Получено {len(logs)} логов для анализа")

                # Обрабатываем только первые N логов для производительности
                max_logs_to_process = 1000
                logs_to_process = logs[:max_logs_to_process]

                for i, log in enumerate(logs_to_process):
                    try:
                        tx_hash = log.get('transactionHash')
                        if not tx_hash:
                            continue

                        # Получаем транзакцию
                        tx = self.web3.eth.get_transaction(tx_hash)
                        if not tx:
                            continue

                        # Проверяем, что это входящая BNB транзакция
                        if (tx.to and
                                tx.to.lower() == address_lower and
                                tx.value and
                                int(tx.value) > 0):

                            # Получаем блок
                            try:
                                block = self.web3.eth.get_block(tx.blockNumber)
                                timestamp = block.timestamp if block else int(time.time())
                            except:
                                timestamp = int(time.time())

                            transactions.append({
                                'hash': tx_hash.hex(),
                                'from': tx['from'],
                                'to': tx['to'],
                                'value': tx['value'],
                                'value_eth': self.web3.from_wei(tx.value, 'ether'),
                                'timestamp': timestamp,
                                'is_native': True,
                                'token': 'BNB',
                                'block_number': tx.blockNumber,
                                'method': 'alternative_logs'
                            })

                    except Exception as e:
                        if i % 100 == 0:  # Логируем только каждую 100-ю ошибку
                            logger.debug(f"Ошибка в альтернативном методе (лог {i}): {e}")
                        continue

                logger.info(f"Альтернативный метод нашел {len(transactions)} транзакций")

        except Exception as e:
            logger.warning(f"Ошибка в альтернативном методе: {e}")

        return transactions

    def get_token_transfers(self, address: str, start_block: int, end_block: int) -> List[Dict]:
        """Получает BEP20 токенные трансферы для адреса"""
        transfers = []

        logger.info(f"BSC: Поиск BEP20 транзакций с {start_block} по {end_block}")

        try:
            # Используем фильтр для Transfer событий
            logs = self._make_rpc_call("eth_getLogs", [{
                "fromBlock": hex(start_block),
                "toBlock": hex(end_block),
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",  # Transfer signature
                    None,  # from (любой)
                    "0x" + address[2:].rjust(64, '0')  # to (наш адрес)
                ]
            }])

            if logs:
                logger.info(f"BSC: Получено {len(logs)} логов Transfer")
                for i, log in enumerate(logs):
                    try:
                        # Парсим данные лога
                        topics = log.get('topics', [])
                        if len(topics) < 3:
                            continue

                        from_address = '0x' + topics[1].hex()[-40:]
                        to_address = '0x' + topics[2].hex()[-40:]

                        # Проверяем, что это входящая транзакция к нашему адресу
                        if to_address.lower() != address.lower():
                            continue

                        # Парсим amount из data
                        data = log.get('data', '0x')
                        if data == '0x':
                            continue

                        amount = int(data, 16)

                        # Получаем информацию о токене
                        token_contract = log.get('address', '').lower()
                        token_symbol = self.BEP20_TOKENS.get(token_contract)

                        # Если токен не в списке, пробуем получить его символ из контракта
                        if not token_symbol:
                            try:
                                token_contract_obj = self.web3.eth.contract(
                                    address=self.web3.to_checksum_address(token_contract),
                                    abi=self.ERC20_ABI
                                )
                                token_symbol = token_contract_obj.functions.symbol().call()
                            except Exception as e:
                                logger.debug(f"Не удалось получить символ токена {token_contract}: {e}")
                                token_symbol = token_contract[:6] + '...' + token_contract[-4:]

                        # Получаем информацию о блоке для timestamp
                        block_number = int(log.get('blockNumber', '0x0'), 16)
                        try:
                            block = self.web3.eth.get_block(block_number)
                            timestamp = block.timestamp if block else 0
                        except:
                            timestamp = 0

                        transfers.append({
                            'hash': log.get('transactionHash', ''),
                            'from': from_address,
                            'to': to_address,
                            'value': amount,
                            'contract_address': token_contract,
                            'token_symbol': token_symbol,
                            'timestamp': timestamp,
                            'is_native': False,
                            'token': token_symbol,
                            'block_number': block_number
                        })

                        # Логируем прогресс
                        if (i + 1) % 100 == 0:
                            logger.debug(f"Обработано {i + 1}/{len(logs)} токенных логов")

                    except Exception as e:
                        logger.warning(f"Ошибка парсинга лога {i}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Ошибка получения токенных трансферов: {e}")

        logger.info(f"BSC: Найдено {len(transfers)} BEP20 транзакций")
        return transfers

    def get_historical_transactions(self, address: str, start_timestamp: int, end_timestamp: int) -> Tuple[
        List[Dict], List[Dict]]:
        """Получает все транзакции за период (и нативные, и токенные)"""
        try:
            # Получаем номера блоков для временного диапазона
            start_block = self.get_block_by_timestamp(start_timestamp)
            end_block = self.get_block_by_timestamp(end_timestamp)

            logger.info(f"BSC: Ищем транзакции с блока {start_block} по {end_block} "
                        f"({end_block - start_block} блоков) для {address[:10]}...")

            # Используем улучшенный метод для нативных BNB
            native_txs = self.parse_native_bnb_transactions(address, start_block, end_block)

            # Получаем токенные транзакции
            token_txs = self.get_token_transfers(address, start_block, end_block)

            logger.info(f"BSC: Итог - {len(native_txs)} нативных BNB и {len(token_txs)} токенных транзакций")

            # Детальный лог
            if native_txs:
                logger.info("Образцы найденных BNB транзакций:")
                for tx in native_txs[:3]:  # Показываем первые 3
                    logger.info(f"  {tx['hash'][:10]}... | {tx['value_eth']} BNB от {tx['from'][:10]}...")

            if token_txs:
                logger.info("Образцы найденных токенных транзакций:")
                for tx in token_txs[:3]:  # Показываем первые 3
                    logger.info(f"  {tx['hash'][:10]}... | {tx['token']} от {tx['from'][:10]}...")

            return native_txs, token_txs

        except Exception as e:
            logger.error(f"Ошибка получения исторических транзакций BSC: {e}")
            return [], []

    def get_current_block(self) -> int:
        """Получает текущий номер блока"""
        try:
            return self.web3.eth.get_block_number()
        except Exception as e:
            logger.error(f"Ошибка получения текущего блока: {e}")
            return 0

    def get_balance(self, address: str) -> Dict:
        """Получает балансы адреса"""
        try:
            # Нативный баланс BNB
            native_balance = self.web3.eth.get_balance(address)
            native_balance_eth = self.web3.from_wei(native_balance, 'ether')

            # Балансы популярных токенов
            token_balances = {}

            for token_addr, token_symbol in self.BEP20_TOKENS.items():
                try:
                    contract = self.web3.eth.contract(
                        address=self.web3.to_checksum_address(token_addr),
                        abi=self.ERC20_ABI
                    )
                    balance = contract.functions.balanceOf(address).call()
                    if balance > 0:
                        # Пробуем получить decimals
                        try:
                            decimals = contract.functions.decimals().call()
                            balance_formatted = balance / (10 ** decimals)
                            token_balances[token_symbol] = {
                                'raw': balance,
                                'formatted': balance_formatted,
                                'decimals': decimals
                            }
                        except:
                            token_balances[token_symbol] = {
                                'raw': balance,
                                'formatted': balance,
                                'decimals': 18
                            }
                except Exception as e:
                    logger.debug(f"Не удалось получить баланс {token_symbol}: {e}")
                    continue

            logger.info(f"Баланс {address[:10]}...: {native_balance_eth} BNB, {len(token_balances)} токенов")

            return {
                'native': {
                    'raw': native_balance,
                    'formatted': native_balance_eth,
                    'symbol': 'BNB'
                },
                'tokens': token_balances
            }

        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return {
                'native': {'raw': 0, 'formatted': 0, 'symbol': 'BNB'},
                'tokens': {}
            }

    def test_address_transactions(self, address: str, hours_back: int = 24) -> Dict:
        """Тестовый метод для проверки транзакций адреса"""
        try:
            end_time = int(time.time())
            start_time = end_time - (hours_back * 3600)

            logger.info(f"Тестируем адрес {address} за последние {hours_back} часов...")

            # Получаем баланс
            balance = self.get_balance(address)

            # Получаем транзакции
            native_txs, token_txs = self.get_historical_transactions(address, start_time, end_time)

            # Сводка
            total_bnb_received = sum(int(tx['value']) for tx in native_txs)
            total_bnb_received_eth = self.web3.from_wei(total_bnb_received, 'ether')

            result = {
                'address': address,
                'balance': balance,
                'native_transactions': {
                    'count': len(native_txs),
                    'total_received': total_bnb_received,
                    'total_received_eth': total_bnb_received_eth,
                    'sample': native_txs[:5] if native_txs else []
                },
                'token_transactions': {
                    'count': len(token_txs),
                    'tokens': list(set(tx['token'] for tx in token_txs)),
                    'sample': token_txs[:5] if token_txs else []
                },
                'time_range': {
                    'start': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time)),
                    'end': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time)),
                    'hours': hours_back
                }
            }

            logger.info(f"Тест завершен: {len(native_txs)} BNB, {len(token_txs)} токенных транзакций")

            return result

        except Exception as e:
            logger.error(f"Ошибка тестирования адреса: {e}")
            return {'error': str(e)}