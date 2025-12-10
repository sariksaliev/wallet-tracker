# config.py
import os
import logging
from dotenv import load_dotenv
from datetime import timezone, timedelta

# Завантажуємо змінні оточення
load_dotenv()

# --- Токены бота ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в .env")

# --- API Ключи ---
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
if not ETHERSCAN_API_KEY:
    raise ValueError("❌ ETHERSCAN_API_KEY не найден в .env")

TRON_API_KEY = os.getenv('TRON_API_KEY')
if not TRON_API_KEY:
    raise ValueError("❌ TRON_API_KEY не найден в .env")

# --- ANKR Premium API (для BNB Chain и других сетей) ---
ANKR_API_KEY = os.getenv('ANKR_API_KEY', 'fa04ad2a4473ae13c6edd204561588fbde88ae1442ac0d81a3f7e92ca8013ccc')
ANKR_ENDPOINT = f"https://rpc.ankr.com/multichain/{ANKR_API_KEY}"

# --- BscScan API (опционально, как fallback) ---
BSCSCAN_API_KEY = os.getenv('BSCSCAN_API_KEY', '')

# --- Часовая зона ---
TZ_UTC_PLUS_3 = timezone(timedelta(hours=3))

# ============================================
#  ПОДДЕРЖИВАЕМЫЕ СЕТИ (ID -> Название)
# ============================================

SUPPORTED_CHAINS = {
    # Ethereum сеть и L2
    1: "Ethereum",
    42161: "Arbitrum One",
    10: "Optimism",
    8453: "Base",
    324: "zkSync Era",

    # EVM-совместимые
    56: "BNB Smart Chain",
    137: "Polygon",
    43114: "Avalanche C-Chain",
    250: "Fantom",
    100: "Gnosis Chain",
    42220: "Celo",
    1313161554: "Aurora",
    25: "Cronos",
    1666600000: "Harmony",
    1284: "Moonbeam",
    1285: "Moonriver",
    8217: "Klaytn",
    1088: "Metis",
    66: "OKC",
    59144: "Linea",
    534352: "Scroll",
    1101: "Polygon zkEVM",

    # Другие
    33139: "ApeChain",
    1329: "Sei",

    # TRON (не EVM, отдельная обработка)
    'tron': "TRON"
}

# ============================================
#  МАППИНГ ДЛЯ ANKR API (ID -> ANKR chain name)
# ============================================

ANKR_CHAIN_MAPPING = {
    1: 'eth',  # Ethereum
    56: 'bsc',  # BNB Smart Chain
    137: 'polygon',  # Polygon
    42161: 'arbitrum',  # Arbitrum One
    10: 'optimism',  # Optimism
    8453: 'base',  # Base
    43114: 'avalanche',  # Avalanche C-Chain
    250: 'fantom',  # Fantom
    100: 'gnosis',  # Gnosis Chain
    42220: 'celo',  # Celo
    1313161554: 'aurora',  # Aurora
    25: 'cronos',  # Cronos
    1666600000: 'harmony',  # Harmony
    1284: 'moonbeam',  # Moonbeam
    1285: 'moonriver',  # Moonriver
    8217: 'klaytn',  # Klaytn
    1088: 'metis',  # Metis
    66: 'okc',  # OKC
    59144: 'linea',  # Linea
    534352: 'scroll',  # Scroll
    1101: 'polygon_zkevm',  # Polygon zkEVM
    324: 'zksync',  # zkSync Era
}

# ============================================
#  НАТИВНЫЕ ТОКЕНЫ СЕТЕЙ
# ============================================

CHAIN_TOKENS = {
    1: "ETH",
    56: "BNB",
    137: "MATIC",
    42161: "ETH",
    10: "ETH",
    8453: "ETH",
    43114: "AVAX",
    250: "FTM",
    100: "xDAI",
    42220: "CELO",
    1313161554: "ETH",
    25: "CRO",
    1666600000: "ONE",
    1284: "GLMR",
    1285: "MOVR",
    8217: "KLAY",
    1088: "METIS",
    66: "OKT",
    59144: "ETH",
    534352: "ETH",
    1101: "ETH",
    324: "ETH",
    33139: "APE",
    1329: "SEI",
    'tron': "TRX"
}

# ============================================
#  EXPLORERS (для ссылок на транзакции)
# ============================================

EXPLORERS = {
    1: "https://etherscan.io/tx/{}",
    56: "https://bscscan.com/tx/{}",
    137: "https://polygonscan.com/tx/{}",
    42161: "https://arbiscan.io/tx/{}",
    10: "https://optimistic.etherscan.io/tx/{}",
    8453: "https://basescan.org/tx/{}",
    43114: "https://snowtrace.io/tx/{}",
    250: "https://ftmscan.com/tx/{}",
    100: "https://gnosisscan.io/tx/{}",
    42220: "https://celoscan.io/tx/{}",
    1313161554: "https://aurorascan.dev/tx/{}",
    25: "https://cronoscan.com/tx/{}",
    1666600000: "https://explorer.harmony.one/tx/{}",
    1284: "https://moonscan.io/tx/{}",
    1285: "https://moonriver.moonscan.io/tx/{}",
    8217: "https://scope.klaytn.com/tx/{}",
    1088: "https://andromeda-explorer.metis.io/tx/{}",
    66: "https://www.oklink.com/okc/tx/{}",
    59144: "https://lineascan.build/tx/{}",
    534352: "https://scrollscan.com/tx/{}",
    1101: "https://zkevm.polygonscan.com/tx/{}",
    324: "https://explorer.zksync.io/tx/{}",
    33139: "https://apescan.io/tx/{}",
    1329: "https://seiscan.io/tx/{}",
}

TRON_EXPLORER = "https://tronscan.org/#/transaction/{}"

# ============================================
#  ИЗВЕСТНЫЕ ТОКЕНЫ
# ============================================

# Популярные TRC20 токены TRON
TRC20_SYMBOLS = {
    'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': 'USDT',  # USDT TRC20
    'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8': 'USDC',  # USDC TRC20
    'TSSMHYeV2uE9qYH95DqyoCuNCzEL1NvU3S': 'SUN',  # SUN
    'TVj7RNVHy6thbM7BWdSe9G6gXwKhjhdNZS': 'JST',  # JST
    'TCFLL5dx5ZJdKnWuesXxi1VPwjLVmWZZy9': 'JST',  # JST (альтернативный)
    'TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7': 'WIN',  # WINkLink
    'TNUC9Qb1rRpS5CbWLmNxN3N8f6zzJP2DPY': 'BTT',  # BTT
    'TKfjV9RNKJJCqPvBtK8L7Knykh7DNWvnYt': 'NFT',  # APENFT
    'TMwFHYXLJaRUPeW6421aqXL4ZEzPRFGkGT': 'USDJ',  # USDJ
    'TFczxzPhnThNSqr5by8tvxsdCFRRz6cPNq': 'DICE',  # TRONbet Dice
}

# Популярные BEP20 токены BNB Chain
BEP20_TOKENS = {
    '0x55d398326f99059ff775485246999027b3197955': 'USDT',
    '0xe9e7cea3dedca5984780bafc599bd69add087d56': 'BUSD',
    '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d': 'USDC',
    '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c': 'WBNB',
    '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82': 'CAKE',
    '0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c': 'BTCB',
    '0x2170ed0880ac9a755fd29b2688956bd959f933f8': 'ETH',
    '0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3': 'DAI',
    '0xba2ae424d960c26247dd6c32edc70b295c744c43': 'DOGE',
    '0x7083609fce4d1d8dc0c979aab8c869ea2c873402': 'DOT',
}

# ============================================
#  НАСТРОЙКИ ПРОИЗВОДИТЕЛЬНОСТИ
# ============================================

# Настройки для BSC RPC (fallback на случай проблем с ANKR)
BSC_RPC_SETTINGS = {
    'max_retries': 3,
    'timeout': 15,
    'max_blocks_to_scan': 5000,
    'direct_block_parse_limit': 200,
}

# ============================================
#  НАСТРОЙКИ ANKR API (PREMIUM ТАРИФ)
# ============================================

# ============================================
#  НАСТРОЙКИ ANKR API (PREMIUM ТАРИФ)
# ============================================

ANKR_SETTINGS = {
    'timeout': 30,           # Таймаут запроса
    'max_retries': 3,        # Максимальное количество попыток
    'batch_size': 50,        # Размер батча для запросов
    'use_websocket': True,   # Использовать WebSocket для мониторинга
}

# ============================================
#  НАСТРОЙКИ ЛОГИРОВАНИЯ
# ============================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================
#  СОСТОЯНИЯ ДЛЯ CONVERSATION HANDLER
# ============================================

ADD_NETWORK = 0
ADD_ADDRESS = 1
REMOVE_ADDRESS, REMOVE_CONFIRM = range(2, 4)
TODAY_WALLET_CHOICE = 4
ADD_SHORTNAME = 5

# ============================================
#  БАЗА ДАННЫХ
# ============================================

DATABASE_FILE = 'wallets.db'

# ============================================
#  НАСТРОЙКИ ОТЧЕТОВ
# ============================================

# Время отправки ежедневного отчета (UTC+3)
DAILY_REPORT_TIME = "00:00"  # Полночь по UTC+3

# Минимальная сумма для отображения (фильтр мусорных транзакций)
MIN_AMOUNT_THRESHOLD = {
    'USDT': 1.0,
    'USDC': 1.0,
    'BUSD': 1.0,
    'BNB': 0.001,
    'ETH': 0.001,
    'TRX': 10.0,
    'MATIC': 1.0,
    'default': 0.01
}