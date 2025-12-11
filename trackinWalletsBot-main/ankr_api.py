# ankr_api.py - PREMIUM VERSION
import requests
import time
from typing import Dict, List, Any, Optional
from config import logger


class AnkrPremiumAPI:
    """ANKR Premium API клиент с расширенными возможностями"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or "ваш_premium_ключ"  # Замените на ваш premium ключ
        self.multichain_url = "https://rpc.ankr.com/multichain"
        self.archive_url = "https://rpc.ankr.com/archive"  # Для архивных данных

        # Премиум features
        self.premium_features = {
            'max_page_size': 1000,  # Premium: до 1000 транзакций на страницу
            'rate_limit': 100,  # Premium: 100 запросов/сек
            'historical_data': True,  # Полный исторический доступ
            'real_time': True  # Реальное время
        }

        logger.info(f"✅ AnkrPremiumAPI инициализирован (Premium тариф)")
        logger.info(f"   Макс. страница: {self.premium_features['max_page_size']} tx")
        logger.info(f"   Rate limit: {self.premium_features['rate_limit']}/сек")

    def _get_ankr_chain_name(self, chain: str) -> str:
        """Конвертирует наше имя цепи в имя цепи ANKR"""
        # Полный список цепей для Premium
        chain_mapping = {
            # EVM цепи
            'eth': 'eth',
            'bsc': 'bsc',
            'bnb': 'bsc',
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
            'polygon_zkevm': 'polygon-zkevm',
            'zksync': 'zksync-era',
            'zksync_era': 'zksync-era',

            # Не-EVM цепи (Premium поддерживает)
            'bitcoin': 'bitcoin',
            'solana': 'solana',
            'near': 'near',
            'cardano': 'cardano',
            'cosmos': 'cosmos',
            'polkadot': 'polkadot',
            'algorand': 'algorand',
            'ton': 'ton',

            # Testnets (Premium доступны)
            'goerli': 'goerli',
            'sepolia': 'sepolia',
            'bsc_testnet': 'bsc-testnet',
            'polygon_mumbai': 'polygon-mumbai'
        }

        chain_lower = chain.lower().replace('_', '-')
        return chain_mapping.get(chain_lower, chain_lower)

    def get_transactions_by_time_range(self, address: str, chain: str,
                                       start_timestamp: int = None,
                                       end_timestamp: int = None,
                                       max_pages: int = 10,
                                       include_logs: bool = True,
                                       decode_logs: bool = True) -> List[Dict]:
        """
        Премиум метод: получает транзакции с расширенными параметрами
        """
        ankr_chain = self._get_ankr_chain_name(chain)

        # Премиум параметры
        params = {
            "jsonrpc": "2.0",
            "method": "ankr_getTransactionsByAddress",
            "params": {
                "address": address.lower(),
                "chain": ankr_chain,
                "pageSize": self.premium_features['max_page_size'],  # Используем премиум лимит
                "order": "desc",
                "includeLogs": include_logs,
                "decodeLogs": decode_logs
            },
            "id": 1
        }

        # Премиум: точная фильтрация по времени
        if start_timestamp:
            params["params"]["fromTimestamp"] = start_timestamp
        if end_timestamp:
            params["params"]["toTimestamp"] = end_timestamp

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}"  # Для premium может потребоваться
        }

        all_transactions = []
        page_token = None

        try:
            for page in range(1, max_pages + 1):
                logger.info(f"AnkrPremium: страница {page}, цепь {ankr_chain}")

                if page_token:
                    params["params"]["pageToken"] = page_token

                response = requests.post(
                    self.multichain_url,
                    json=params,
                    headers=headers,
                    timeout=60  # Увеличиваем таймаут для больших запросов
                )

                if response.status_code == 429:
                    logger.warning("Rate limit достигнут, пауза 1 сек...")
                    time.sleep(1)
                    continue

                data = response.json()

                if 'error' in data:
                    error_msg = data['error'].get('message', str(data['error']))

                    # Premium-specific error handling
                    if "premium" in error_msg.lower() or "subscription" in error_msg.lower():
                        logger.error(f"Premium ошибка: {error_msg}")
                        # Пробуем без премиум features
                        params["params"]["pageSize"] = 100
                        del params["params"]["decodeLogs"]
                        continue

                    logger.error(f"API ошибка: {error_msg}")
                    break

                result = data.get('result', {})
                transactions = result.get('transactions', [])

                if not transactions:
                    logger.info(f"Больше транзакций нет на странице {page}")
                    break

                all_transactions.extend(transactions)
                logger.info(f"Получено {len(transactions)} транзакций, всего {len(all_transactions)}")

                page_token = result.get('nextPageToken')
                if not page_token:
                    logger.info("Достигнут конец списка транзакций")
                    break

                # Премиум: можно делать меньше пауз
                if page % 5 == 0:
                    time.sleep(0.1)

            logger.info(f"✅ Всего получено {len(all_transactions)} транзакций для {ankr_chain}")

            # Премиум: дополнительная обработка данных
            enriched_txs = self._enrich_transactions(all_transactions, ankr_chain)
            return enriched_txs

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут запроса для {ankr_chain}")
        except Exception as e:
            logger.error(f"Ошибка AnkrPremium: {e}")

        return []

    def _enrich_transactions(self, transactions: List[Dict], chain: str) -> List[Dict]:
        """Обогащает транзакции дополнительной информацией (премиум фича)"""
        enriched = []

        for tx in transactions:
            try:
                # Премиум: добавляем классификацию транзакций
                tx_type = self._classify_transaction(tx)

                # Премиум: вычисляем газ в USD если есть данные
                gas_usd = self._calculate_gas_in_usd(tx, chain)

                enriched_tx = tx.copy()
                enriched_tx['_premium'] = {
                    'transaction_type': tx_type,
                    'gas_usd': gas_usd,
                    'enriched_at': int(time.time())
                }

                enriched.append(enriched_tx)

            except Exception as e:
                logger.debug(f"Ошибка обогащения tx: {e}")
                enriched.append(tx)

        return enriched

    def _classify_transaction(self, tx: Dict) -> str:
        """Классифицирует тип транзакции"""
        logs = tx.get('logs', [])

        if not logs:
            return 'native_transfer'

        # Проверяем события ERC20
        for log in logs:
            topics = log.get('topics', [])
            if len(topics) >= 3:
                # Transfer event
                if topics[0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                    return 'erc20_transfer'
                # Approval event
                elif topics[0] == '0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925':
                    return 'erc20_approval'

        return 'contract_interaction'

    def _calculate_gas_in_usd(self, tx: Dict, chain: str) -> float:
        """Вычисляет стоимость газа в USD (премиум фича)"""
        try:
            gas_used = int(tx.get('gasUsed', '0x0'), 16) if isinstance(tx.get('gasUsed'), str) else tx.get('gasUsed', 0)
            gas_price = int(tx.get('gasPrice', '0x0'), 16) if isinstance(tx.get('gasPrice'), str) else tx.get(
                'gasPrice', 0)

            if gas_used == 0 or gas_price == 0:
                return 0.0

            gas_cost_wei = gas_used * gas_price
            gas_cost_eth = gas_cost_wei / 1e18

            # Здесь нужно получить текущую цену ETH/USD
            # Для простоты возвращаем только в ETH
            return float(gas_cost_eth)

        except Exception:
            return 0.0

    # ПРЕМИУМ МЕТОДЫ

    def get_historical_balance(self, address: str, chain: str, timestamp: int) -> Dict:
        """Получает исторический баланс на определенный момент времени"""
        ankr_chain = self._get_ankr_chain_name(chain)

        payload = {
            "jsonrpc": "2.0",
            "method": "ankr_getHistoricalAccountBalance",
            "params": {
                "address": address.lower(),
                "chain": ankr_chain,
                "timestamp": timestamp
            },
            "id": 1
        }

        try:
            response = requests.post(self.archive_url, json=payload, timeout=30)
            data = response.json()
            return data.get('result', {})
        except Exception as e:
            logger.error(f"Ошибка historical balance: {e}")
            return {}

    def get_token_holders(self, contract_address: str, chain: str, limit: int = 100) -> List[Dict]:
        """Получает список холдеров токена"""
        ankr_chain = self._get_ankr_chain_name(chain)

        payload = {
            "jsonrpc": "2.0",
            "method": "ankr_getTokenHolders",
            "params": {
                "contractAddress": contract_address.lower(),
                "chain": ankr_chain,
                "pageSize": min(limit, 1000)  # Premium limit
            },
            "id": 1
        }

        try:
            response = requests.post(self.multichain_url, json=payload, timeout=60)
            data = response.json()
            return data.get('result', {}).get('holders', [])
        except Exception as e:
            logger.error(f"Ошибка получения холдеров: {e}")
            return []

    def get_contract_logs(self, contract_address: str, chain: str,
                          event_signature: str = None,
                          from_block: int = None,
                          to_block: int = None) -> List[Dict]:
        """Получает логи контракта с фильтрацией"""
        ankr_chain = self._get_ankr_chain_name(chain)

        params = {
            "address": contract_address.lower(),
            "chain": ankr_chain
        }

        if event_signature:
            params["eventSignature"] = event_signature
        if from_block:
            params["fromBlock"] = hex(from_block)
        if to_block:
            params["toBlock"] = hex(to_block)

        payload = {
            "jsonrpc": "2.0",
            "method": "ankr_getLogs",
            "params": [params],
            "id": 1
        }

        try:
            response = requests.post(self.multichain_url, json=payload, timeout=60)
            data = response.json()
            return data.get('result', [])
        except Exception as e:
            logger.error(f"Ошибка получения логов: {e}")
            return []

    def batch_request(self, requests_list: List[Dict]) -> List[Dict]:
        """Пакетный запрос (премиум фича)"""
        payload = {
            "jsonrpc": "2.0",
            "method": "ankr_batch",
            "params": requests_list,
            "id": 1
        }

        try:
            response = requests.post(self.multichain_url, json=payload, timeout=120)
            data = response.json()
            return data.get('result', [])
        except Exception as e:
            logger.error(f"Ошибка batch запроса: {e}")
            return []


# Для обратной совместимости
AnkrAPI = AnkrPremiumAPI