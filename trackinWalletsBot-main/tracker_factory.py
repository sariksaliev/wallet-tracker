# tracker_factory.py
import time
from typing import Dict, Any, Optional, List, Union
from config import logger, ANKR_CHAIN_MAPPING, CHAIN_TOKENS, BEP20_TOKENS, TRC20_SYMBOLS


class TrackerFactory:
    """Фабрика для создания трекеров под разные сети"""

    @staticmethod
    def create_tracker(network: str, **kwargs) -> Any:
        """
        Создает трекер для указанной сети
        """
        network = network.lower()

        if network == 'tron':
            return TronTracker(**kwargs)

        elif network == 'bnb':
            return BnbTracker(**kwargs)

        elif network in ['eth', 'ethereum']:
            return EthTracker(**kwargs)

        elif network in ['polygon', 'arbitrum', 'optimism', 'base', 'avalanche',
                         'fantom', 'gnosis', 'celo', 'aurora', 'cronos', 'harmony',
                         'moonbeam', 'moonriver', 'klaytn', 'metis', 'okc',
                         'linea', 'scroll', 'polygon_zkevm', 'zksync']:
            return EVMTracker(network, **kwargs)

        else:
            # По умолчанию пробуем ANKR
            logger.warning(f"Сеть {network} не определена, пробуем ANKR...")
            return EVMTracker(network, **kwargs)


# ============================================
#  БАЗОВЫЙ КЛАСС ТРЕКЕРА
# ============================================

class BaseTracker:
    """Базовый класс для всех трекеров"""

    def __init__(self, network: str):
        self.network = network
        self.api = None

    def get_transactions(self, address: str, start_time: int = None, end_time: int = None, **kwargs) -> Dict:
        """Базовый метод - должен быть переопределен в наследниках"""
        raise NotImplementedError("Метод должен быть реализован в наследнике")

    def filter_by_time(self, transactions: List[Dict], start_time: int, end_time: int) -> List[Dict]:
        """Фильтрует транзакции по временному диапазону"""
        filtered = []
        for tx in transactions:
            timestamp = tx.get('timestamp', 0)
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue
            filtered.append(tx)
        return filtered


# ============================================
#  ТРЕКЕР ДЛЯ TRON
# ============================================

class TronTracker(BaseTracker):
    """Трекер для сети TRON (через TronGrid)"""

    def __init__(self, **kwargs):
        try:
            from trongrid_api import TronGridAPI
            api_key = kwargs.get('tron_api_key')
            self.api = TronGridAPI(api_key=api_key) if api_key else TronGridAPI()
            super().__init__('tron')
            logger.info(f"✅ TronTracker инициализирован")
        except ImportError as e:
            logger.error(f"Не удалось импортировать TronGridAPI: {e}")
            raise

    def get_transactions(self, address: str, start_time: int = None, end_time: int = None, **kwargs):
        """Получает транзакции TRON"""
        logger.info(f"TronTracker: получение транзакций для {address[:10]}...")

        # Нативные TRX транзакции
        native_txs = self.api.get_chain_transactions(address)
        parsed_native = self._parse_native_txs(native_txs, address)

        # TRC20 токены
        trc20_txs = self.api.get_trc20_transfers(address)
        parsed_trc20 = self._parse_trc20_txs(trc20_txs, address)

        # Фильтруем по времени если нужно
        if start_time or end_time:
            parsed_native = self.filter_by_time(parsed_native, start_time, end_time)
            parsed_trc20 = self.filter_by_time(parsed_trc20, start_time, end_time)

        return {
            'native': parsed_native,
            'tokens': parsed_trc20,
            'network': 'tron'
        }

    def _parse_native_txs(self, transactions, target_address):
        """Парсит нативные TRX транзакции"""
        parsed = []
        target_lower = target_address.lower()

        for tx in transactions:
            try:
                contract = tx.get('raw_data', {}).get('contract', [{}])[0]
                if contract.get('type') != 'TransferContract':
                    continue

                value = contract.get('parameter', {}).get('value', {})
                to_address = value.get('to_address', '').lower()

                if to_address != target_lower:
                    continue

                amount_raw = int(value.get('amount', 0))
                amount = amount_raw / 1e6  # TRX имеет 6 decimals

                if amount <= 0:
                    continue

                timestamp_ms = tx.get('raw_data', {}).get('timestamp', 0)
                timestamp = timestamp_ms // 1000 if timestamp_ms else int(time.time())

                parsed.append({
                    'hash': tx.get('txID', ''),
                    'from': value.get('owner_address', ''),
                    'to': to_address,
                    'value': amount,
                    'value_raw': amount_raw,
                    'timestamp': timestamp,
                    'token': 'TRX',
                    'is_native': True,
                    'network': 'tron'
                })
            except Exception as e:
                logger.warning(f"Ошибка парсинга TRX транзакции: {e}")
                continue

        logger.info(f"TronTracker: найдено {len(parsed)} нативных TRX транзакций")
        return parsed

    def _parse_trc20_txs(self, transfers, target_address):
        """Парсит TRC20 токены"""
        parsed = []
        target_lower = target_address.lower()

        for transfer in transfers:
            try:
                to_address = transfer.get('to', '').lower()
                if to_address != target_lower:
                    continue

                token_info = transfer.get('token_info', {})
                contract_address = transfer.get('contract_address', '')

                # Пропускаем если токен не USDT/USDC или не в списке известных
                symbol = token_info.get('symbol', 'UNKNOWN')
                if symbol == 'UNKNOWN':
                    symbol = TRC20_SYMBOLS.get(contract_address.lower(), 'UNKNOWN')

                amount_raw = int(transfer.get('value', 0))
                decimals = int(token_info.get('decimals', 6))
                amount = amount_raw / (10 ** decimals)

                if amount <= 0:
                    continue

                timestamp_ms = transfer.get('block_timestamp', 0)
                timestamp = timestamp_ms // 1000 if timestamp_ms else int(time.time())

                parsed.append({
                    'hash': transfer.get('transaction_id', ''),
                    'from': transfer.get('from', ''),
                    'to': to_address,
                    'value': amount,
                    'value_raw': amount_raw,
                    'contract_address': contract_address,
                    'token_symbol': symbol,
                    'timestamp': timestamp,
                    'is_native': False,
                    'network': 'tron'
                })
            except Exception as e:
                logger.warning(f"Ошибка парсинга TRC20: {e}")
                continue

        logger.info(f"TronTracker: найдено {len(parsed)} TRC20 транзакций")
        return parsed


# ============================================
#  ТРЕКЕР ДЛЯ BNB CHAIN
# ============================================

class BnbTracker(BaseTracker):
    """Трекер для BNB Chain (через ANKR)"""

    def __init__(self, **kwargs):
        try:
            from ankr_api import AnkrAPI
            ankr_api_key = kwargs.get('ankr_api_key')
            if not ankr_api_key:
                logger.error("❌ ANKR API ключ не указан для BnbTracker")
                raise ValueError("ANKR API ключ не указан")

            self.api = AnkrAPI(ankr_api_key)
            super().__init__('bnb')
            logger.info(f"✅ BnbTracker инициализирован с ANKR API")

        except ImportError as e:
            logger.error(f"Не удалось импортировать AnkrAPI: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка инициализации BnbTracker: {e}")
            raise

    def get_transactions(self, address: str, start_time: int = None, end_time: int = None, **kwargs):
        """Получает транзакции BNB Chain через ANKR"""
        logger.info(f"BnbTracker: получение транзакций для {address[:10]}...")

        # Получаем транзакции за период
        ankr_transactions = self.api.get_transactions_by_time_range(
            address=address,
            chain='bsc',  # ANKR использует 'bsc' для BNB Chain
            start_timestamp=start_time,
            end_timestamp=end_time,
            max_pages=3
        )

        if not ankr_transactions:
            logger.info(f"BnbTracker: транзакций не найдено")
            return {
                'native': [],
                'tokens': [],
                'network': 'bnb'
            }

        # Парсим и разделяем
        native_txs = []
        token_txs = []

        for tx in ankr_transactions:
            try:
                # Базовые поля
                tx_hash = tx.get('hash', '')
                tx_from = tx.get('from', '').lower()
                tx_to = tx.get('to', '').lower()

                # Конвертируем значение из hex в int
                tx_value_raw = tx.get('value', '0x0')
                if isinstance(tx_value_raw, str) and tx_value_raw.startswith('0x'):
                    tx_value = int(tx_value_raw, 16)
                else:
                    tx_value = int(tx_value_raw) if tx_value_raw else 0

                tx_timestamp = tx.get('timestamp', 0)

                # Проверяем, что это входящая транзакция
                if tx_to.lower() != address.lower():
                    continue

                # 1. Нативная BNB транзакция
                if tx_value > 0:
                    native_txs.append({
                        'hash': tx_hash,
                        'from': tx_from,
                        'to': tx_to,
                        'value': tx_value / 1e18,  # BNB: 18 decimals
                        'value_raw': tx_value,
                        'timestamp': tx_timestamp,
                        'token': 'BNB',
                        'is_native': True,
                        'network': 'bnb'
                    })

                # 2. Токенные транзакции (из логов)
                logs = tx.get('logs', [])
                for log in logs:
                    topics = log.get('topics', [])
                    if len(topics) >= 3 and topics[
                        0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                        # Transfer событие ERC20/BEP20
                        to_addr = '0x' + topics[2][-40:] if len(topics[2]) >= 40 else ''

                        if to_addr.lower() != address.lower():
                            continue

                        # Парсим amount
                        data_hex = log.get('data', '0x')
                        if data_hex.startswith('0x'):
                            data_hex = data_hex[2:]

                        amount_raw = int(data_hex, 16) if data_hex else 0
                        if amount_raw <= 0:
                            continue

                        contract_addr = log.get('address', '').lower()
                        token_symbol = BEP20_TOKENS.get(contract_addr, 'UNKNOWN')

                        # По умолчанию 18 decimals для BEP20
                        amount = amount_raw / 1e18

                        token_txs.append({
                            'hash': tx_hash,
                            'from': '0x' + topics[1][-40:] if len(topics[1]) >= 40 else '',
                            'to': to_addr,
                            'value': amount,
                            'value_raw': amount_raw,
                            'contract_address': contract_addr,
                            'token_symbol': token_symbol,
                            'timestamp': tx_timestamp,
                            'is_native': False,
                            'network': 'bnb'
                        })

            except Exception as e:
                logger.warning(f"Ошибка парсинга BNB транзакции: {e}")
                continue

        logger.info(f"BnbTracker: найдено {len(native_txs)} BNB и {len(token_txs)} BEP20 транзакций")

        return {
            'native': native_txs,
            'tokens': token_txs,
            'network': 'bnb'
        }


# ============================================
#  ТРЕКЕР ДЛЯ ETHEREUM
# ============================================

class EthTracker(BaseTracker):
    """Трекер для Ethereum (через Etherscan)"""

    def __init__(self, **kwargs):
        try:
            from etherscan_api import EtherscanAPI
            api_key = kwargs.get('etherscan_api_key')
            chain_id = kwargs.get('chain_id', 1)
            self.api = EtherscanAPI(api_key=api_key, chain_id=chain_id) if api_key else EtherscanAPI(chain_id=chain_id)
            super().__init__('eth')
            logger.info(f"✅ EthTracker инициализирован (chain_id: {chain_id})")
        except ImportError as e:
            logger.error(f"Не удалось импортировать EtherscanAPI: {e}")
            raise

    def get_transactions(self, address: str, start_time: int = None, end_time: int = None, **kwargs):
        """Получает транзакции Ethereum через Etherscan"""
        logger.info(f"EthTracker: получение транзакций для {address[:10]}...")

        # Нативные транзакции
        native_txs = self.api.get_chain_transactions(address) or []

        # Токенные транзакции
        token_txs = self.api.get_token_transactions(address) or []

        # Парсим
        parsed_native = self._parse_transactions(native_txs, address, is_native=True)
        parsed_tokens = self._parse_transactions(token_txs, address, is_native=False)

        # Фильтруем по времени
        if start_time or end_time:
            parsed_native = self.filter_by_time(parsed_native, start_time, end_time)
            parsed_tokens = self.filter_by_time(parsed_tokens, start_time, end_time)

        logger.info(f"EthTracker: найдено {len(parsed_native)} ETH и {len(parsed_tokens)} ERC20 транзакций")

        return {
            'native': parsed_native,
            'tokens': parsed_tokens,
            'network': 'eth'
        }

    def _parse_transactions(self, transactions, target_address, is_native=True):
        """Парсит транзакции Etherscan"""
        parsed = []
        target_lower = target_address.lower()

        for tx in transactions:
            try:
                to_address = tx.get('to', '').lower()
                if to_address != target_lower:
                    continue

                value = int(tx.get('value', 0))
                if value <= 0:
                    continue

                timestamp = int(tx.get('timeStamp', 0))

                if is_native:
                    amount = value / 1e18
                    token = 'ETH'
                else:
                    decimals = int(tx.get('tokenDecimal', 18))
                    amount = value / (10 ** decimals)
                    token = tx.get('tokenSymbol', 'UNKNOWN')

                parsed.append({
                    'hash': tx.get('hash'),
                    'from': tx.get('from', ''),
                    'to': to_address,
                    'value': amount,
                    'value_raw': value,
                    'timestamp': timestamp,
                    'token': token,
                    'is_native': is_native,
                    'contract_address': tx.get('contractAddress') if not is_native else None,
                    'network': 'eth'
                })
            except Exception as e:
                logger.warning(f"Ошибка парсинга {'native' if is_native else 'token'} tx: {e}")
                continue

        return parsed


# ============================================
#  ТРЕКЕР ДЛЯ ДРУГИХ EVM СЕТЕЙ
# ============================================

class EVMTracker(BaseTracker):
    """Трекер для других EVM сетей (через ANKR)"""

    def __init__(self, network: str, **kwargs):
        try:
            from ankr_api import AnkrAPI
            ankr_api_key = kwargs.get('ankr_api_key')
            if not ankr_api_key:
                logger.error(f"❌ ANKR API ключ не указан для EVMTracker ({network})")
                raise ValueError("ANKR API ключ не указан")

            self.api = AnkrAPI(ankr_api_key)
            super().__init__(network)

            # Маппинг сети на ANKR chain name
            self.ankr_chain_names = {
                'polygon': 'polygon',
                'arbitrum': 'arbitrum',
                'optimism': 'optimism',
                'base': 'base',
                'avalanche': 'avalanche',
                'fantom': 'fantom',
                'gnosis': 'gnosis',
                'celo': 'celo',
                'aurora': 'aurora',
                'cronos': 'cronos',
                'harmony': 'harmony',
                'moonbeam': 'moonbeam',
                'moonriver': 'moonriver',
                'klaytn': 'klaytn',
                'metis': 'metis',
                'okc': 'okc',
                'linea': 'linea',
                'scroll': 'scroll',
                'polygon_zkevm': 'polygon_zkevm',
                'zksync': 'zksync'
            }

            self.ankr_chain = self.ankr_chain_names.get(network.lower(), network.lower())
            logger.info(f"✅ EVMTracker инициализирован для {network} -> ANKR chain: {self.ankr_chain}")

        except ImportError as e:
            logger.error(f"Не удалось импортировать AnkrAPI: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка инициализации EVMTracker для {network}: {e}")
            raise

    def get_transactions(self, address: str, start_time: int = None, end_time: int = None, **kwargs):
        """Получает транзакции через ANKR"""
        logger.info(f"EVMTracker[{self.network}]: получение транзакций для {address[:10]}...")

        # Получаем транзакции через ANKR
        ankr_transactions = self.api.get_transactions_by_time_range(
            address=address,
            chain=self.ankr_chain,
            start_timestamp=start_time,
            end_timestamp=end_time,
            max_pages=2
        )

        if not ankr_transactions:
            logger.info(f"EVMTracker[{self.network}]: транзакций не найдено")
            return {
                'native': [],
                'tokens': [],
                'network': self.network
            }

        # Нативный токен сети
        native_token = CHAIN_TOKENS.get(self._get_chain_id(), 'UNKNOWN')

        # Парсим
        native_txs = []
        token_txs = []

        for tx in ankr_transactions:
            try:
                tx_to = tx.get('to', '').lower()
                if tx_to != address.lower():
                    continue

                # Конвертируем значение из hex в int
                tx_value_raw = tx.get('value', '0x0')
                if isinstance(tx_value_raw, str) and tx_value_raw.startswith('0x'):
                    tx_value = int(tx_value_raw, 16)
                else:
                    tx_value = int(tx_value_raw) if tx_value_raw else 0

                tx_timestamp = tx.get('timestamp', 0)

                # Нативная транзакция
                if tx_value > 0:
                    native_txs.append({
                        'hash': tx.get('hash', ''),
                        'from': tx.get('from', ''),
                        'to': tx_to,
                        'value': tx_value / 1e18,  # По умолчанию 18 decimals
                        'value_raw': tx_value,
                        'timestamp': tx_timestamp,
                        'token': native_token,
                        'is_native': True,
                        'network': self.network
                    })

                # Токенные транзакции (опционально, можно добавить)
                logs = tx.get('logs', [])
                for log in logs:
                    topics = log.get('topics', [])
                    if len(topics) >= 3 and topics[
                        0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                        # Transfer событие
                        to_addr = '0x' + topics[2][-40:] if len(topics[2]) >= 40 else ''

                        if to_addr.lower() != address.lower():
                            continue

                        data_hex = log.get('data', '0x')
                        if data_hex.startswith('0x'):
                            data_hex = data_hex[2:]

                        amount_raw = int(data_hex, 16) if data_hex else 0
                        if amount_raw <= 0:
                            continue

                        contract_addr = log.get('address', '').lower()
                        token_symbol = 'UNKNOWN'  # Нужна база токенов для каждой сети

                        amount = amount_raw / 1e18

                        token_txs.append({
                            'hash': tx.get('hash', ''),
                            'from': '0x' + topics[1][-40:] if len(topics[1]) >= 40 else '',
                            'to': to_addr,
                            'value': amount,
                            'value_raw': amount_raw,
                            'contract_address': contract_addr,
                            'token_symbol': token_symbol,
                            'timestamp': tx_timestamp,
                            'is_native': False,
                            'network': self.network
                        })

            except Exception as e:
                logger.warning(f"Ошибка парсинга {self.network} транзакции: {e}")
                continue

        logger.info(
            f"EVMTracker[{self.network}]: найдено {len(native_txs)} нативных и {len(token_txs)} токенных транзакций")

        return {
            'native': native_txs,
            'tokens': token_txs,
            'network': self.network
        }

    def _get_chain_id(self) -> int:
        """Определяет chain_id по названию сети"""
        mapping = {
            'polygon': 137,
            'arbitrum': 42161,
            'optimism': 10,
            'base': 8453,
            'avalanche': 43114,
            'fantom': 250,
            'gnosis': 100,
            'celo': 42220,
            'aurora': 1313161554,
            'cronos': 25,
            'harmony': 1666600000,
            'moonbeam': 1284,
            'moonriver': 1285,
            'klaytn': 8217,
            'metis': 1088,
            'okc': 66,
            'linea': 59144,
            'scroll': 534352,
            'polygon_zkevm': 1101,
            'zksync': 324
        }
        return mapping.get(self.network.lower(), 1)