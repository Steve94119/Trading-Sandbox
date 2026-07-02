from datetime import timedelta
from pathlib import Path
from typing import Final


API_TIMEOUT_SEC: Final = 10
CBR_CACHE_TTL: Final = timedelta(hours=1)

CBR_BASE_URL: Final = "http://www.cbr.ru/scripts"
CRYPTO_BASE_URL: Final = "https://api.coinlore.net"

DB_PATH: Final = Path("data/trading_sandbox.db")
DB_HISTORY_LIMIT: Final = 50

START_BALANCE: Final = 10000.0
REFRESH_INTERVAL_MS: Final = 30000
CLOCK_TICK_MS: Final = 1000
CRYPTO_LIMIT: Final = 20
CHART_HISTORY_DAYS: Final = 7
CHART_HISTORY_DAYS: Final = 7
CBR_HISTORY_DAYS: Final = 30

CBR_CODES_20: Final = [
    "USD", "EUR", "CNY", "GBP", "JPY", "CHF", "KZT", "BYN", "TRY", "INR",
    "AUD", "CAD", "HKD", "KGS", "MDL", "NOK", "PLN", "SEK", "CZK", "KRW",
]

CBR_HISTORY_IDS: Final = {
    "USD": "R01235", "EUR": "R01239", "GBP": "R01010", "JPY": "R01820",
    "CHF": "R01775", "CNY": "R01375", "KZT": "R01335", "BYN": "R01090",
    "TRY": "R01720", "INR": "R01270", "AUD": "R01060", "CAD": "R01350",
    "HKD": "R01200", "KGS": "R01370", "MDL": "R01500", "NOK": "R01535",
    "PLN": "R01565", "SEK": "R01570", "CZK": "R01660", "KRW": "R01610",
}

DEFAULT_CRYPTO_IDS: Final = ["90", "80", "2"]

FALLBACK_CRYPTO: Final = [
    {"id": "90", "symbol": "BTC", "name": "Bitcoin"},
    {"id": "80", "symbol": "ETH", "name": "Ethereum"},
    {"id": "518", "symbol": "USDT", "name": "Tether"},
    {"id": "2710", "symbol": "BNB", "name": "BNB"},
    {"id": "33285", "symbol": "USDC", "name": "USD Coin"},
    {"id": "58", "symbol": "LTC", "name": "Litecoin"},
    {"id": "48543", "symbol": "SOL", "name": "Solana"},
    {"id": "2713", "symbol": "TRX", "name": "TRON"},
    {"id": "148109", "symbol": "AVAX", "name": "Avalanche"},
    {"id": "158405", "symbol": "MATIC", "name": "Polygon"},
    {"id": "46971", "symbol": "DOT", "name": "Polkadot"},
    {"id": "2", "symbol": "DOGE", "name": "Dogecoin"},
    {"id": "33833", "symbol": "LINK", "name": "Chainlink"},
    {"id": "33422", "symbol": "NEAR", "name": "Near Protocol"},
    {"id": "134", "symbol": "XRP", "name": "XRP"},
    {"id": "89", "symbol": "BCH", "name": "Bitcoin Cash"},
    {"id": "65945", "symbol": "ATOM", "name": "Cosmos"},
    {"id": "96901", "symbol": "ICP", "name": "Internet Computer"},
    {"id": "28", "symbol": "XMR", "name": "Monero"},
    {"id": "257", "symbol": "ETC", "name": "Ethereum Classic"},
]

DATE_FORMATS: Final = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
)