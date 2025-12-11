# ankr_api.py
import requests
import time
from typing import Dict, List, Any, Optional
from config import logger, ANKR_CHAIN_MAPPING


class AnkrAPI:
    """ANKR API клиент с отдельными endpoint'ами для каждой сети"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or "fa04ad2a4473ae13c6edd204561588fbde88ae1442ac0d81a3f7e92ca8013ccc"
        logger.info(f"✅ AnkrAPI инициализирован с ключом: ...{self.api_key[-8:]}")

    def _get_endpoint(self, chain: str) -> str:
        """Возвращает endpoint для конкретной цепи"""
        # Базовые endpoint'ы для основных сетей
        endpoints = {
            'eth': f'https://rpc.ankr.com/eth/{self.api_key}',
            'bsc': f'https://rpc.ankr.com/bsc/{self.api_key}',
            'polygon': f'https://rpc.ankr.com/polygon/{self.api_key}',
            'arbitrum': f'https://rpc.ankr.com/arbitrum/{self.api_key}',
            'optimism': f'https://rpc.ankr.com/optimism/{self.api_key}',
            'base': f'https://rpc.ankr.com/base/{self.api_key}',
            'avalanche': f'https://rpc.ankr.com/avalanche/{self.api_key}',
            'fantom': f'https://rpc.ankr.com/fantom/{self.api_key}',
            'gnosis': f'https://rpc.ankr.com/gnosis/{self.api_key}',
            'celo': f'https://rpc.ankr.com/celo/{self.api_key}',
            'aurora': f'https://rpc.ankr.com/aurora/{self.api_key}',
            'cronos': f'https://rpc.ankr.com/cronos/{self.api_key}',
            'harmony': f'https://rpc.ankr.com/harmony/{self.api_key}',
        }

        if chain not in endpoints:
            # Пробуем общий формат для других сетей
            return f'https://rpc.ankr.com/{chain}/{self.api_key}'

        return endpoints[chain]

    def get_transactions_by_time_range(self, address: str, chain: str,
                                       start_timestamp: int = None,
                                       end_timestamp: int = None,
                                       max_pages: int = 3) -> List[Dict]:
        """
        Получает транзакции для адреса за указанный период
        """
        endpoint = self._get_endpoint(chain)

        # ANKR JSON-RPC метод для получения транзакций
        method = "ankr_getTransactionsByAddress"

        params = {
            "address": address.lower(),
            "chain": chain,  # Имя цепи для ANKR
            "fromBlock": "latest",
            "toBlock": "latest",
            "pageSize": 100
        }

        # Если задан диапазон времени, добавляем фильтры
        if start_timestamp:
            params["fromTimestamp"] = start_timestamp
        if end_timestamp:
            params["toTimestamp"] = end_timestamp

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": [params],
            "id": 1
        }

        try:
            logger.info(f"AnkrAPI: запрос транзакций {chain} для {address[:10]}...")
            response = requests.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()

            if 'error' in data:
                logger.error(f"AnkrAPI ошибка для {chain}: {data['error']}")
                return []

            transactions = data.get('result', {}).get('transactions', [])

            # Если ANKR не фильтрует по времени, фильтруем на клиенте
            if (start_timestamp or end_timestamp) and transactions:
                filtered = []
                for tx in transactions:
                    tx_time = tx.get('timestamp', 0)
                    if start_timestamp and tx_time < start_timestamp:
                        continue
                    if end_timestamp and tx_time > end_timestamp:
                        continue
                    filtered.append(tx)
                transactions = filtered

            logger.info(f"AnkrAPI: получено {len(transactions)} транзакций для {chain}")
            return transactions

        except Exception as e:
            logger.error(f"Ошибка AnkrAPI для {chain}: {e}")
            return []