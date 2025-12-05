import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import logger, TRON_API_KEY


class TronGridAPI:
    BASE_URL = "https://api.trongrid.io/v1"

    def __init__(self, api_key: str = TRON_API_KEY):
        if not api_key:
            logger.error("Ключ API TronGrid не предоставлен!")
            raise ValueError("API ключ TronGrid отсутствует")
        self.api_key = api_key
        self.headers = {'TRON-PRO-API-KEY': api_key}

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError)),
        before_sleep=lambda retry_state: logger.info(
            f"Повторная попытка запроса в TronGrid (попытка {retry_state.attempt_number}/5): {retry_state.outcome.exception()}"
        )
    )
    def _request(self, url: str, params: dict = None):
        response = requests.get(url, params=params or {}, headers=self.headers, timeout=20)
        response.raise_for_status()
        return response.json()

    def get_chain_transactions(self, address: str) -> list:
        """Отримує нативні транзакції (TRX) для адреси."""
        url = f"{self.BASE_URL}/accounts/{address}/transactions"
        params = {
            "limit": 100,
            "order_by": "block_timestamp,desc",
        }
        try:
            data = self._request(url, params)
            if not data.get('success', True):
                return []
            txs = data.get('data', [])
            return [tx for tx in txs if tx.get('ret', [{}])[0].get('contractRet') == 'SUCCESS']
        except Exception as e:
            logger.error(f"Помилка get_native_transactions: {e}")
            return []

    def get_trc20_transfers(self, address: str) -> list:
        url = f"{self.BASE_URL}/accounts/{address}/transactions/trc20"
        params = {"limit": 100, "order_by": "block_timestamp,desc"}

        try:
            data = self._request(url, params)
            if not data.get('success', True):
                logger.warning(f"TronGrid trc20 не success: {data}")
                return []
            return data.get('trc20', data.get('data', []))
        except Exception as e:
            logger.error(f"Ошибка get_trc20_transfers: {e}")
            return []