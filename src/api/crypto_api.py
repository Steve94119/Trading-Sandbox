from datetime import UTC, datetime
from typing import Dict, List

import requests
from requests import RequestException

BASE_URL = "https://api.coinlore.net"
DEFAULT_TIMEOUT = 10


def get_crypto_rates(coin_ids: List[str] = ["90", "80", "2"]) -> Dict[str, Dict[str, float | str]]:
    url = f"{BASE_URL}/api/ticker/"
    ids = ",".join(coin_ids)

    try:
        resp = requests.get(url, params={"id": ids}, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except RequestException as e:
        raise RuntimeError(f"Не удалось получить курсы криптовалют: {e}") from e
    except ValueError as e:
        raise RuntimeError("Не удалось декодировать ответ") from e

    result = {}
    for item in data:
        coin_id = item.get("id")
        if not coin_id:
            continue
        result[coin_id] = {
            "symbol": item.get("symbol", ""),
            "name": item.get("name", ""),
            "price_usd": float(item.get("price_usd")),
            "percent_change_24h": float(item.get("percent_change_24h")),
            "percent_change_1h": float(item.get("percent_change_1h")),
        }
    return result


def get_top_crypto(limit: int = 20) -> List[Dict[str, float | str]]:
    url = f"{BASE_URL}/api/tickers/"

    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except RequestException as e:
        raise RuntimeError(f"Не удалось получить список криптовалют: {e}") from e
    except ValueError as e:
        raise RuntimeError("Не удалось декодировать ответ") from e

    items = payload.get("data", []) if isinstance(payload, dict) else payload
    result = []
    for item in items[:limit]:
        result.append({
            "id": str(item.get("id", "")),
            "symbol": item.get("symbol", ""),
            "name": item.get("name", ""),
        })
    return result


def get_crypto_history(coin_id: str, days: int = 7) -> List[Dict[str, float | int | str]]:
    url = f"{BASE_URL}/api/coin/ohlcv/"

    try:
        resp = requests.get(url, params={"coin": coin_id}, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except RequestException as e:
        raise RuntimeError(f"Не удалось получить историю: {e}") from e
    except ValueError as e:
        raise RuntimeError("Не удалось декодировать ответ") from e

    last = data[-days:]
    result = []
    for row in last:
        timestamp = row[0]
        open_, high, low, close, volume = row[1], row[2], row[3], row[4], row[5]

        try:
            date = datetime.fromtimestamp(int(timestamp), UTC).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError, OSError):
            date = ""

        result.append({
            "date": date,
            "timestamp": int(timestamp),
            "open": float(open_),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume),
        })
    return result


if __name__ == "__main__":
    # Тут у меня просто тесты(они не вызываются при импорте из других модулей)
    print(get_crypto_rates())
    print(get_crypto_history(coin_id="90", days=7))
    print(get_top_crypto(20))
