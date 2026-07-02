from datetime import datetime, timedelta
from typing import Dict, List
from xml.etree import ElementTree

import requests
from requests import RequestException

BASE_URL = "http://www.cbr.ru/scripts"
DEFAULT_TIMEOUT = 10
CACHE_TTL = timedelta(hours=1)

cache_data = None
cache_time = None


def get_currency_rates(date=None) -> Dict[str, Dict[str, float | int | str]]:
    global cache_data, cache_time

    if date is None and cache_data is not None and cache_time is not None:
        if datetime.now() - cache_time < CACHE_TTL:
            return cache_data

    params = {}
    if date is not None:
        params["date_req"] = format_date(date)

    try:
        resp = requests.get(f"{BASE_URL}/XML_daily.asp", params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
    except RequestException as e:
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
        cache_data = result
        cache_time = datetime.now()

    return result


def get_currency_history(currency_code, from_date, to_date) -> List[Dict[str, float | str]]:
    params = {
        "VAL_NM_RQ": currency_code,
        "date_req1": format_date(from_date),
        "date_req2": format_date(to_date),
    }

    try:
        resp = requests.get(f"{BASE_URL}/XML_dynamic.asp", params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
    except RequestException as e:
        raise RuntimeError(f"Не удалось получить историю валюты ЦБ: {e}") from e
    except ElementTree.ParseError as e:
        raise RuntimeError("Не удалось разобрать XML") from e

    result = []
    for item in root.findall("Record"):
        result.append({
            "date": item.attrib.get("Date", ""),
            "value": float(item.findtext("Value", default="0").replace(",", ".")),
        })
    return result


def format_date(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    return value


if __name__ == "__main__":
    # Тут у меня просто тесты(они не вызываются при импорте из других модулей)
    print(get_currency_rates())
    print(get_currency_history("R01235", "01/06/2026", "30/06/2026"))
