# Trading Sandbox

Десктоп-приложение на PyQt5 — виртуальная торговая песочница по валютам
и криптовалютам. Курсы подтягиваются из открытых API, сделки проводятся на
виртуальном балансе, история и снимки портфеля сохраняются в локальную SQLite.

## Возможности

- **Вкладка «Валюты»** — 20 самых популярных валют ЦБ РФ (USD, EUR, CNY, GBP, JPY,
  CHF, KZT, BYN, TRY, INR, AUD, CAD, HKD, KGS, MDL, NOK, PLN, SEK, CZK, KRW).
  Клик по строке открывает график истории за 30 дней в рублях. Купить/продать
  с указанием стоп-лосса и тейк-профита.
- **Вкладка «Криптовалюты»** — топ-20 монет с CoinLore (BTC, ETH, USDT, BNB,
  SOL и др.). Цены автоматически пересчитываются в рубли по текущему курсу USD.
  Клик по строке — график OHLCV за 7 дней. Купить/продать, SL/TP.
- **Вкладка «Портфель»** — стоимость, кэш, PnL, текущие активы и история
  сделок. Можно сохранить снимок портфеля и выгрузить историю в CSV.
- **Авто-обновление** каждые 30 секунд.
- **Стоп-лосс / тейк-профит** — при пересечении уровня сделка закрывается
  автоматически на ближайшем обновлении цен.

## Установка и запуск

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

## Использованные API

- **CoinLore** (`https://api.coinlore.net`) — список тикеров, текущие цены и
  OHLCV-история криптовалют. Ключ не требуется.
- **API ЦБ РФ** (`http://www.cbr.ru/scripts`) — ежедневные курсы валют и
  динамика по конкретной валюте (`XML_daily.asp`, `XML_dynamic.asp`). Ключ не
  требуется.

## Структура

```
main.py                  # точка входа
config.py                # все настройки (URL, лимиты, тикеры, fallback)
requirements.txt
src/
  api/                   # cbr_api, crypto_api
  gui/                   # main_window, RatesService, MainWindow
  models/                # VirtualPortfolio, Order, TradingEngine
  utils/                 # PriceChart, DatabaseManager
data/                    # SQLite база (trading_sandbox.db)
```
