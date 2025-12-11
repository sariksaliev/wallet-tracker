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
ANKR_PREMIUM = True  # Флаг для премиум тарифа

# Отдельные endpoint'ы для каждой сети
ANKR_ENDPOINTS = {
    'eth': f'https://rpc.ankr.com/eth/{ANKR_API_KEY}',
    'bsc': f'https://rpc.ankr.com/bsc/{ANKR_API_KEY}',
    'bnb': f'https://rpc.ankr.com/bsc/{ANKR_API_KEY}',  # Алиас для BNB
    'polygon': f'https://rpc.ankr.com/polygon/{ANKR_API_KEY}',
    'arbitrum': f'https://rpc.ankr.com/arbitrum/{ANKR_API_KEY}',
    'optimism': f'https://rpc.ankr.com/optimism/{ANKR_API_KEY}',
    'base': f'https://rpc.ankr.com/base/{ANKR_API_KEY}',
    'avalanche': f'https://rpc.ankr.com/avalanche/{ANKR_API_KEY}',
    'fantom': f'https://rpc.ankr.com/fantom/{ANKR_API_KEY}',
    'gnosis': f'https://rpc.ankr.com/gnosis/{ANKR_API_KEY}',
    'celo': f'https://rpc.ankr.com/celo/{ANKR_API_KEY}',
    'aurora': f'https://rpc.ankr.com/aurora/{ANKR_API_KEY}',
    'cronos': f'https://rpc.ankr.com/cronos/{ANKR_API_KEY}',
    'harmony': f'https://rpc.ankr.com/harmony/{ANKR_API_KEY}',
    'moonbeam': f'https://rpc.ankr.com/moonbeam/{ANKR_API_KEY}',
    'moonriver': f'https://rpc.ankr.com/moonriver/{ANKR_API_KEY}',
    'klaytn': f'https://rpc.ankr.com/klaytn/{ANKR_API_KEY}',
    'metis': f'https://rpc.ankr.com/metis/{ANKR_API_KEY}',
    'okc': f'https://rpc.ankr.com/okc/{ANKR_API_KEY}',
    'linea': f'https://rpc.ankr.com/linea/{ANKR_API_KEY}',
    'scroll': f'https://rpc.ankr.com/scroll/{ANKR_API_KEY}',
    'polygon_zkevm': f'https://rpc.ankr.com/polygon-zkevm/{ANKR_API_KEY}',
    'zksync': f'https://rpc.ankr.com/zksync-era/{ANKR_API_KEY}',
}

# Multichain API для специальных методов ANKR
ANKR_MULTICHAIN_URL = "https://rpc.ankr.com/multichain"
ANKR_ARCHIVE_URL = "https://rpc.ankr.com/archive"  # Для архивных данных

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

# Обратное маппинг (ANKR chain name -> chain_id)
ANKR_CHAIN_TO_ID = {v: k for k, v in ANKR_CHAIN_MAPPING.items()}

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

# Популярные ERC20 токены (для всех EVM сетей)
ERC20_TOKENS = {
    # USDT на разных сетях
    '0xdac17f958d2ee523a2206206994597c13d831ec7': 'USDT',  # Ethereum
    '0xc2132d05d31c914a87c6611c10748aeb04b58e8f': 'USDT',  # Polygon
    '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9': 'USDT',  # Arbitrum
    '0x94b008aa00579c1307b0ef2c499ad98a8ce58e58': 'USDT',  # Optimism

    # USDC на разных сетях
    '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USDC',  # Ethereum
    '0x2791bca1f2de4661ed88a30c99a7a9449aa84174': 'USDC',  # Polygon
    '0xff970a61a04b1ca14834a43f5de4533ebddb5cc8': 'USDC',  # Arbitrum
    '0x7f5c764cbc14f9669b88837ca1490cca17c31607': 'USDC',  # Optimism

    # DAI
    '0x6b175474e89094c44da98b954eedeac495271d0f': 'DAI',  # Ethereum
    '0x8f3cf7ad23cd3cadbd9735aff958023239c6a063': 'DAI',  # Polygon
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

ANKR_SETTINGS = {
    'timeout': 30,  # Таймаут запроса
    'max_retries': 3,  # Максимальное количество попыток
    'batch_size': 100,  # Размер батча для запросов (премиум: 100+)
    'use_websocket': False,  # Использовать WebSocket для мониторинга

    # Настройки для премиум тарифа
    'premium': {
        'max_page_size': 1000,  # Максимальное количество транзакций на страницу
        'max_pages': 20,  # Максимальное количество страниц
        'rate_limit_delay': 0.05,  # Задержка между запросами (сек)
        'enable_archive': True,  # Включить архивные данные
        'decode_logs': True,  # Автоматическое декодирование логов
        'include_internal_txs': True,  # Включать внутренние транзакции
    }
}


# ============================================
#  НАСТРОЙКИ ЛОГИРОВАНИЯ
# ============================================

# Создаем кастомный форматтер для более читаемых логов
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',  # Cyan
        'INFO': '\033[32m',  # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',  # Red
        'CRITICAL': '\033[41m',  # Red background
        'RESET': '\033[0m'  # Reset
    }

    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
            record.msg = f"{self.COLORS[record.levelname.split('m')[1] + 'm']}{record.msg}{self.COLORS['RESET']}"
        return super().format(record)


# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Консольный хендлер с цветами
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = ColoredFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(console_formatter)

# Файловый хендлер
file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Очистка старых хендлеров и добавление новых
if logger.hasHandlers():
    logger.handlers.clear()

logger.addHandler(console_handler)
logger.addHandler(file_handler)

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
    'AVAX': 0.1,
    'FTM': 1.0,
    'default': 0.01
}

# Настройки для разных типов отчетов
REPORT_SETTINGS = {
    'daily': {
        'enabled': True,
        'time': "00:00",  # UTC+3
        'include_tokens': True,
        'min_amount': MIN_AMOUNT_THRESHOLD,  # ИСПРАВЛЕНО
        'format': 'detailed'  # detailed/summary
    },
    'weekly': {
        'enabled': True,
        'day': 'monday',  # Понедельник
        'time': "09:00",
        'format': 'summary'
    },
    'monthly': {
        'enabled': True,
        'day': 1,  # Первое число месяца
        'time': "10:00",
        'format': 'summary'
    }
}

# ============================================
#  НАСТРОЙКИ ТРЕКЕРА
# ============================================

TRACKER_SETTINGS = {
    'max_transactions_per_request': 1000,  # Для премиум тарифа
    'transaction_timeout': 60,  # Таймаут для получения транзакций
    'cache_duration': 300,  # Длительность кэша в секундах (5 минут)
    'retry_on_failure': True,
    'retry_delay': 2,
    'max_retries': 3,
}

# ============================================
#  НАСТРОЙКИ БОТА
# ============================================

BOT_SETTINGS = {
    'admin_ids': [],  # ID администраторов бота
    'max_wallets_per_user': 20,  # Максимальное количество кошельков на пользователя
    'cooldown_seconds': 2,  # Задержка между командами
    'welcome_message': True,  # Отправлять приветственное сообщение
    'notify_on_error': True,  # Уведомлять об ошибках
}

# ============================================
#  КЭШИРОВАНИЕ
# ============================================

CACHE_SETTINGS = {
    'enabled': True,
    'ttl': 300,  # Time to live в секундах (5 минут)
    'max_size': 1000,  # Максимальное количество элементов в кэше
}

# ============================================
#  СИСТЕМНЫЕ НАСТРОЙКИ
# ============================================

SYSTEM_SETTINGS = {
    'debug': False,  # Режим отладки
    'test_mode': False,  # Тестовый режим (не отправляет реальные сообщения)
    'maintenance': False,  # Режим технического обслуживания
}


# Проверка обязательных переменных окружения
def check_environment():
    """Проверка корректности настроек окружения"""
    required = ['TELEGRAM_TOKEN', 'ETHERSCAN_API_KEY', 'TRON_API_KEY']
    missing = [var for var in required if not os.getenv(var)]

    if missing:
        raise ValueError(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing)}")

    # Проверка ANKR API ключа если используется премиум
    if ANKR_PREMIUM and not ANKR_API_KEY.startswith('fa04ad2a'):
        logger.info(f"✅ Используется премиум ANKR API ключ")
    else:
        logger.warning(f"⚠️ Используется бесплатный ANKR API ключ. Ограничения могут применяться.")

    logger.info(f"✅ Конфигурация загружена успешно")
    logger.info(f"   Поддерживаемые сети: {len(SUPPORTED_CHAINS)}")
    logger.info(f"   ANKR Премиум: {'Да' if ANKR_PREMIUM else 'Нет'}")


# Автоматическая проверка при импорте
check_environment()