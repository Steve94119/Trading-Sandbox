from datetime import datetime
from xml.etree import ElementTree

import requests

from config import CBR_BASE_URL, CBR_CACHE_TTL, API_TIMEOUT_SEC


def _format_date(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    return value


class CBRApi:
    def __init__(self, base_url: str = CBR_BASE_URL, timeout: int = API_TIMEOUT_SEC,
                 cache_ttl=None) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.cache_ttl = cache_ttl or CBR_CACHE_TTL
        self._cache = None
        self._cache_time = None

    def get_currency_rates(self, date=None) -> dict:
        if date is None and self._is_cache_fresh():
            return self._cache

        params = {} if date is None else {"date_req": _format_date(date)}

        try:
            resp = requests.get(f"{self.base_url}/XML_daily.asp",
                                params=params, timeout=self.timeout)
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.content)
        except requests.RequestException as e:
            raise RuntimeError(f"Не удалось получить курсы валют ЦБ: {e}") from e
        except ElementTree.ParseError as e:
            raise RuntimeError("Не удалось разобрать XML") from e

        result = {}
        for item in root.findall("Valute"):
            code = item.findtext("CharCode", default="")
            if not code:
                continue
            result[code] = {
                "name": item.findtext("Name", default=""),
                "value": float(item.findtext("Value", default="0").replace(",", ".")),
                "nominal": int(item.findtext("Nominal", default="1")),
            }

        if date is None:
            self._cache = result
            self._cache_time = datetime.now()
        return result

    def get_currency_history(self, currency_code, from_date, to_date) -> list:
        params = {
            "VAL_NM_RQ": currency_code,
            "date_req1": _format_date(from_date),
            "date_req2": _format_date(to_date),
        }
        try:
            resp = requests.get(f"{self.base_url}/XML_dynamic.asp",
                                params=params, timeout=self.timeout)
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.content)
        except requests.RequestException as e:
            raise RuntimeError(f"Не удалось получить историю валюты ЦБ: {e}") from e
        except ElementTree.ParseError as e:
            raise RuntimeError("Не удалось разобрать XML") from e

        return [
            {
                "date": item.attrib.get("Date", ""),
                "value": float(item.findtext("Value", default="0").replace(",", ".")),
            }
            for item in root.findall("Record")
        ]

    def _is_cache_fresh(self) -> bool:
        return (self._cache is not None and self._cache_time is not None
                and datetime.now() - self._cache_time < self.cache_ttl)