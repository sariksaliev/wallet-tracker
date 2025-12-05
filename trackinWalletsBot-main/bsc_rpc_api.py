import requests
import time
from typing import List, Dict, Optional, Tuple
from web3 import Web3
from config import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class BscRPCError(Exception):
    pass


class BscRPC:
    """RPC клиент для BNB Smart Chain"""

    # Список публичных RPC узлов BSC
    RPC_ENDPOINTS = [
        "https://bsc-dataseed.binance.org",
        "https://bsc-dataseed1.binance.org",
        "https://bsc-dataseed1.defibit.io",
        "https://bsc-dataseed2.defibit.io",
        "https://bsc-dataseed3.defibit.io",
        "https://bsc-dataseed4.defibit.io",
    ]

    # ERC20 ABI для парсинга токенов
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
        for i in range(len(self.RPC_ENDPOINTS)):
            endpoint = self.RPC_ENDPOINTS[(self.current_endpoint + i) % len(self.RPC_ENDPOINTS)]
            try:
                self.web3 = Web3(Web3.HTTPProvider(endpoint, request_kwargs={'timeout': 30}))
                if self.web3.is_connected():
                    logger.info(f"✅ Подключено к BSC RPC: {endpoint}")
                    self.current_endpoint = (self.current_endpoint + i) % len(self.RPC_ENDPOINTS)
                    return
            except Exception as e:
                logger.warning(f"Не удалось подключиться к {endpoint}: {e}")

        raise BscRPCError("Не удалось подключиться ни к одному RPC узлу BSC")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type((requests.exceptions.RequestException, BscRPCError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Повтор BSC RPC запроса (попытка {retry_state.attempt_number}/3)"
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
                timeout=30
            )

            if response.status_code != 200:
                raise BscRPCError(f"HTTP ошибка {response.status_code}")

            data = response.json()

            if 'error' in data:
                error_msg = data['error'].get('message', 'Unknown error')
                raise BscRPCError(f"RPC ошибка: {error_msg}")

            return data.get('result')

        except Exception as e:
            logger.error(f"Ошибка RPC вызова: {e}")
            # Пробуем другой endpoint при ошибке
            self.current_endpoint = (self.current_endpoint + 1) % len(self.RPC_ENDPOINTS)
            self._connect()
            raise

    def get_block_by_timestamp(self, timestamp: int) -> int:
        """Получает номер блока по timestamp (приблизительно)"""
        try:
            latest_block = self.web3.eth.get_block('latest')
            latest_timestamp = latest_block.timestamp
            latest_number = latest_block.number

            # Линейная аппроксимация
            if timestamp > latest_timestamp:
                return latest_number

            # Среднее время блока в BSC ~3 секунды
            avg_block_time = 3
            blocks_diff = int((latest_timestamp - timestamp) / avg_block_time)
            target_block = max(1, latest_number - blocks_diff)

            return target_block

        except Exception as e:
            logger.error(f"Ошибка получения блока по timestamp: {e}")
            # Возвращаем приблизительное значение
            return max(1, self.web3.eth.get_block_number() - int((time.time() - timestamp) / 3))

    def get_transactions(self, address: str, start_block: int, end_block: int) -> List[Dict]:
        """Получает нативные транзакции BNB для адреса"""
        # Формируем фильтр для получения транзакций
        from_block = hex(start_block)
        to_block = hex(end_block)

        # Получаем логи событий (для входящих транзакций)
        logs = self._make_rpc_call("eth_getLogs", [{
            "fromBlock": from_block,
            "toBlock": to_block,
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",  # Transfer событие
                None,  # from
                self.web3.to_hex(self.web3.to_bytes(hexstr=address))  # to
            ]
        }])

        transactions = []

        if logs:
            for log in logs:
                # Это может быть как BNB, так и BEP20 токен
                # Для нативных BNB проверяем value > 0 в транзакции
                tx_hash = log.get('transactionHash')
                if tx_hash:
                    try:
                        tx = self.web3.eth.get_transaction(tx_hash)
                        if tx and tx.to and tx.to.lower() == address.lower() and tx.value > 0:
                            transactions.append({
                                'hash': tx_hash.hex(),
                                'from': tx['from'],
                                'to': tx['to'],
                                'value': tx['value'],
                                'timestamp': self.web3.eth.get_block(tx.blockNumber).timestamp,
                                'is_native': True,
                                'token': 'BNB'
                            })
                    except Exception as e:
                        logger.warning(f"Не удалось получить транзакцию {tx_hash}: {e}")

        return transactions

    def get_token_transfers(self, address: str, start_block: int, end_block: int) -> List[Dict]:
        """Получает BEP20 токенные трансферы для адреса"""
        # Фильтр для Transfer событий
        logs = self._make_rpc_call("eth_getLogs", [{
            "fromBlock": hex(start_block),
            "toBlock": hex(end_block),
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",  # Transfer signature
                None,  # from (любой)
                self.web3.to_hex(self.web3.to_bytes(hexstr=address))  # to (наш адрес)
            ]
        }])

        transfers = []

        if logs:
            for log in logs:
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
                        except:
                            token_symbol = token_contract[:6] + '...' + token_contract[-4:]

                    # Получаем информацию о блоке для timestamp
                    block_number = int(log.get('blockNumber', '0x0'), 16)
                    block = self.web3.eth.get_block(block_number)

                    transfers.append({
                        'hash': log.get('transactionHash', ''),
                        'from': from_address,
                        'to': to_address,
                        'value': amount,
                        'contract_address': token_contract,
                        'token_symbol': token_symbol,
                        'timestamp': block.timestamp if block else 0,
                        'is_native': False,
                        'token': token_symbol
                    })

                except Exception as e:
                    logger.warning(f"Ошибка парсинга лога: {e}")

        return transfers

    def get_historical_transactions(self, address: str, start_timestamp: int, end_timestamp: int) -> Tuple[
        List[Dict], List[Dict]]:
        """Получает все транзакции за период (и нативные, и токенные)"""
        try:
            # Получаем номера блоков для временного диапазона
            start_block = self.get_block_by_timestamp(start_timestamp)
            end_block = self.get_block_by_timestamp(end_timestamp)

            logger.info(f"BSC: Ищем транзакции с блока {start_block} по {end_block} для {address[:10]}...")

            # Получаем нативные транзакции
            native_txs = self.get_transactions(address, start_block, end_block)

            # Получаем токенные транзакции
            token_txs = self.get_token_transfers(address, start_block, end_block)

            logger.info(f"BSC: Найдено {len(native_txs)} нативных и {len(token_txs)} токенных транзакций")

            return native_txs, token_txs

        except Exception as e:
            logger.error(f"Ошибка получения исторических транзакций BSC: {e}")
            return [], []