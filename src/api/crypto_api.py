from datetime import UTC, datetime

import requests

from config import CRYPTO_BASE_URL, API_TIMEOUT_SEC, DEFAULT_CRYPTO_IDS


class CryptoApi:
    def __init__(self, base_url: str = CRYPTO_BASE_URL,
                 timeout: int = API_TIMEOUT_SEC) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def get_crypto_rates(self, coin_ids=None) -> dict:
        ids = coin_ids or DEFAULT_CRYPTO_IDS
        try:
            resp = requests.get(
                f"{self.base_url}/api/ticker/",
                params={"id": ",".join(ids)},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
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

    def get_top_crypto(self, limit: int = 20) -> list:
        try:
            resp = requests.get(f"{self.base_url}/api/tickers/", timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Не удалось получить список криптовалют: {e}") from e
        except ValueError as e:
            raise RuntimeError("Не удалось декодировать ответ") from e

        items = payload.get("data", []) if isinstance(payload, dict) else payload
        return [
            {"id": str(item.get("id", "")),
             "symbol": item.get("symbol", ""),
             "name": item.get("name", "")}
            for item in items[:limit]
        ]

    def get_crypto_history(self, coin_id: str, days: int = 7) -> list:
        try:
            resp = requests.get(
                f"{self.base_url}/api/coin/ohlcv/",
                params={"coin": coin_id},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Не удалось получить историю: {e}") from e
        except ValueError as e:
            raise RuntimeError("Не удалось декодировать ответ") from e

        result = []
        for row in data[-days:]:
            timestamp, open_, high, low, close, volume = row
            try:
                date = datetime.fromtimestamp(int(timestamp), UTC).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
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