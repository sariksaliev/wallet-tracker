import os
import logging
from dotenv import load_dotenv
from datetime import timezone, timedelta

# Завантажуємо змінні оточення
load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
TRON_API_KEY = os.getenv('TRON_API_KEY')

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в .env")

if not ETHERSCAN_API_KEY:
    raise ValueError("❌ ETHERSCAN_API_KEY не найден в .env")

# Часова зона
TZ_UTC_PLUS_3 = timezone(timedelta(hours=3))

SUPPORTED_CHAINS = {
    1: "Ethereum",
    56: "BNB Chain",
    42161: "Arbitrum One",
    #10: "Optimism",
    8453: "Base",
    137: "Polygon",
    #43114: "Avalanche C-Chain",
    33139: "ApeChain",
    59144: "Linea",
    1329: "Sei"
}

CHAIN_TOKENS = {
    1: "ETH",
    42161: "ETH",
    #10: "ETH",
    8453: "ETH",
    137: "MATIC",
    56: "BNB",
    #43114: "AVAX",
    33139: "APE",
    59144: "ETH",
    1329: "SEI"
}

EXPLORERS = {
    1: "https://etherscan.io/tx/{}",
    42161: "https://arbiscan.io/tx/{}",
    #10: "https://optimistic.etherscan.io/tx/{}",
    8453: "https://basescan.org/tx/{}",
    137: "https://polygonscan.com/tx/{}",
    56: "https://bscscan.com/tx/{}",
    #43114: "https://snowtrace.io/tx/{}",
    33139: "https://apescan.io/tx/{}",
    59144: "https://lineascan.build/tx/{}",
    1329: "https://seiscan.io/tx/{}"
}

TRON_EXPLORER = "https://tronscan.org/#/transaction/{}"

TRC20_SYMBOLS = {
    '41a614f803b6fd780986a42c78ec9c7f77e6ded13c': 'USDT',
    'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': 'USDT',
    '41eaa3f0d3d9e0f3f7a0b1c5f3a0b1c5f3a0b1c5f3': 'TUSD',
    'TKyfkjD9xG1dK4nU4hXQ6fX1bJc1s4B2S6': 'TUSD',
    'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8': 'USDC'
}

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Стани для ConversationHandler
ADD_NETWORK = 0
ADD_ADDRESS = 1
REMOVE_ADDRESS, REMOVE_CONFIRM = range(2, 4)
TODAY_WALLET_CHOICE = 4
ADD_SHORTNAME = 5

# Назва файлу БД
DATABASE_FILE = 'wallets.db'