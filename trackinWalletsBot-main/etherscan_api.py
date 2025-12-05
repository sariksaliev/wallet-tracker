import requests
import time
from config import logger, CHAIN_TOKENS
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class EtherscanAPIError(Exception):
    pass


class EtherscanAPI:
    """
    Универсальный клиент для Etherscan API V2.
    Поддерживает все EVM-сети через параметр chainid.
    Возвращает данные в формате list, совместимом с текущей логикой бота.
    """

    BASE_URL = "https://api.etherscan.io/v2/api"

    def __init__(self, api_key: str, chain_id: int = 1):
        if not api_key:
            logger.error("Ключ API Etherscan не предоставлен!")
            raise ValueError("API ключ Etherscan отсутствует")

        self.api_key = api_key
        self.chain_id = chain_id

    def get_native_token(self) -> str:
        return CHAIN_TOKENS.get(self.chain_id, "UNKNOWN")

    # ---- Запрос с повторными попытками ----
    @retry(
        stop=stop_after_attempt(20),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type(
            (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, EtherscanAPIError)
        ),
        before_sleep=lambda st: logger.warning(
            f"Повторная попытка запроса Etherscan V2 ({st.attempt_number}/20)"
        ),
        reraise=True
    )
    def _make_request(self, params: dict):

        params["apikey"] = self.api_key
        params["chainid"] = self.chain_id

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)

            if response.status_code != 200:
                raise EtherscanAPIError(f"HTTP ошибка {response.status_code}: {response.text}")

            data = response.json()

            # Новый формат API V2 всегда содержит поле "result"
            result = data.get("result")
            if result is None:
                logger.warning(f"[Etherscan V2] Пустой result. chainid={self.chain_id}")
                return None

            # --- Случай №1: result = list ---
            if isinstance(result, list):
                return result

            # --- Случай №2: result = dict ---
            if isinstance(result, dict):

                # Важно: токенные транзакции
                if "erc20Transfers" in result:
                    return result["erc20Transfers"]

                # Нативные транзакции
                if "transactions" in result:
                    return result["transactions"]

                # Возможны другие ключи, Etherscan иногда меняет формат
                for key in result:
                    if isinstance(result[key], list):
                        return result[key]

            logger.error(f"[Etherscan V2] Неизвестный формат ответа: {data}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"[Etherscan V2] Ошибка запроса: {e}")
            raise EtherscanAPIError(f"Ошибка запроса: {e}")

        except Exception as e:
            logger.error(f"[Etherscan V2] Ошибка API: {e}")
            raise EtherscanAPIError(str(e))

    # ==============================
    #  PUBLIC METHODS
    # ==============================

    def get_chain_transactions(self, address: str) -> list | None:
        """
        Нативные транзакции сети (ETH, BNB, MATIC, ARB, BASE и т.д.)
        """
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "sort": "desc"
        }
        time.sleep(1)
        return self._make_request(params)

    def get_token_transactions(self, address: str) -> list | None:
        """
        Токенные транзакции сети (ERC20, BEP20, Polygon tokens и т.д.)
        """
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "sort": "desc"
        }
        time.sleep(1)
        return self._make_request(params)
