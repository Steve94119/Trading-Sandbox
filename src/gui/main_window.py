from datetime import datetime, timedelta

import sqlite3
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.api import cbr_api, crypto_api
from src.models.trading_sandbox import Order, TradingEngine, VirtualPortfolio
from src.utils.chart import PriceChart
from src.utils.database import DatabaseManager

CBR_CODES_20 = [
    "USD", "EUR", "CNY", "GBP", "JPY", "CHF", "KZT", "BYN", "TRY", "INR",
    "AUD", "CAD", "HKD", "KGS", "MDL", "NOK", "PLN", "SEK", "CZK", "KRW",
]
CBR_HISTORY_IDS = {
    "USD": "R01235", "EUR": "R01239", "GBP": "R01010", "JPY": "R01820",
    "CHF": "R01775", "CNY": "R01375", "KZT": "R01335", "BYN": "R01090",
    "TRY": "R01720", "INR": "R01270", "AUD": "R01060", "CAD": "R01350",
    "HKD": "R01200", "KGS": "R01370", "MDL": "R01500", "NOK": "R01535",
    "PLN": "R01565", "SEK": "R01570", "CZK": "R01660", "KRW": "R01610",
}
CRYPTO_LIMIT = 20
REFRESH_INTERVAL = 30000

FALLBACK_CRYPTO = [
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
]  # fallback на случай сбоя /api/tickers/


class RatesService(QObject):
    rates_ready = pyqtSignal(dict, dict, list)
    error = pyqtSignal(str)
    history_ready = pyqtSignal(str, list, str, str)

    def __init__(self) -> None:
        super().__init__()
        self.crypto_ids: list[str] = ["90", "80", "2"]

    def fetch_all(self) -> None:
        meta: list[dict] = []
        try:
            meta = crypto_api.get_top_crypto(CRYPTO_LIMIT)
            if not meta:
                raise RuntimeError("empty list")
            self.crypto_ids = [m["id"] for m in meta if m.get("id")]
        except RuntimeError as e:
            self.error.emit(f"CoinLore (список): {e}")
            meta = list(FALLBACK_CRYPTO)
            self.crypto_ids = [m["id"] for m in meta]

        if not self.crypto_ids:
            meta = list(FALLBACK_CRYPTO)
            self.crypto_ids = [m["id"] for m in meta]

        try:
            cbr_data = cbr_api.get_currency_rates()
        except RuntimeError as e:
            cbr_data = {}
            self.error.emit(f"CBR: {e}")

        try:
            crypto_data = crypto_api.get_crypto_rates(self.crypto_ids)
        except RuntimeError as e:
            crypto_data = {}
            self.error.emit(f"CoinLore (rates): {e}")

        self.rates_ready.emit(cbr_data, crypto_data, list(zip(self.crypto_ids, meta)))

    def fetch_history(self, kind: str, asset: str, display_name: str) -> None:
        try:
            if kind == "cbr":
                today = datetime.now()
                data = cbr_api.get_currency_history(
                    asset, (today - timedelta(days=30)).strftime("%d/%m/%Y"),
                    today.strftime("%d/%m/%Y"),
                )
            else:
                data = crypto_api.get_crypto_history(asset, days=7)
        except RuntimeError as e:
            self.error.emit(str(e))
            data = []

        self.history_ready.emit(asset, data, kind, display_name)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Trading Sandbox")
        self.resize(1100, 700)

        self.portfolio = VirtualPortfolio()
        self.engine = TradingEngine(self.portfolio)
        self.db = DatabaseManager()
        self.service = RatesService()
        self.service.rates_ready.connect(self._on_rates_ready)
        self.service.history_ready.connect(self._on_history_ready)
        self.service.error.connect(self._on_service_error)

        self.cbr_prices: dict = {}
        self.crypto_prices: dict = {}
        self.crypto_meta: list[tuple[str, dict]] = []
        self.last_update = None
        self.selected_row_cbr = -1
        self.selected_row_crypto = -1

        self._build_menu()
        self._build_tabs()
        self._build_status_bar()
        self._apply_style()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all)
        self.refresh_timer.start(REFRESH_INTERVAL)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick_clock)
        self.clock_timer.start(1000)

        QtCore.QTimer.singleShot(0, self._refresh_all)

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Файл")
        export_action = QAction("Экспорт CSV", self)
        export_action.triggered.connect(self._export_csv)
        file_menu.addAction(export_action)
        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        menu_bar.addMenu("Настройки")

    def _build_tabs(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_currencies_tab(), "Валюты")
        tabs.addTab(self._build_crypto_tab(), "Криптовалюты")
        tabs.addTab(self._build_portfolio_tab(), "Портфель")
        self.setCentralWidget(tabs)

    def _build_currencies_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.cbr_table = QTableWidget(0, 5)
        self.cbr_table.setHorizontalHeaderLabels(
            ["Код", "Название", "Цена (RUB)", "Номинал", "Курс за 1"]
        )
        self.cbr_table.verticalHeader().setVisible(False)
        self.cbr_table.setAlternatingRowColors(True)
        self.cbr_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cbr_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cbr_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cbr_table.cellClicked.connect(self._on_cbr_row_clicked)
        layout.addWidget(self.cbr_table)

        self.cbr_chart = PriceChart()
        self.cbr_chart.plot.setTitle("Выбери валюту, кликнув по строке", color="#888", size="10pt")
        layout.addWidget(self.cbr_chart, stretch=1)

        btn_row = QHBoxLayout()
        buy_btn = QPushButton("Купить")
        buy_btn.clicked.connect(lambda: self._make_trade("cbr", "buy"))
        sell_btn = QPushButton("Продать")
        sell_btn.clicked.connect(lambda: self._make_trade("cbr", "sell"))
        btn_row.addWidget(buy_btn)
        btn_row.addWidget(sell_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return widget

    def _build_crypto_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.crypto_table = QTableWidget(0, 5)
        self.crypto_table.setHorizontalHeaderLabels(
            ["Тикер", "Название", "Цена (RUB)", "1ч %", "24ч %"]
        )
        self.crypto_table.verticalHeader().setVisible(False)
        self.crypto_table.setAlternatingRowColors(True)
        self.crypto_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.crypto_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.crypto_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.crypto_table.cellClicked.connect(self._on_crypto_row_clicked)
        layout.addWidget(self.crypto_table)

        self.crypto_chart = PriceChart()
        self.crypto_chart.plot.setTitle("Выбери монету, кликнув по строке", color="#888", size="10pt")
        layout.addWidget(self.crypto_chart, stretch=1)

        btn_row = QHBoxLayout()
        buy_btn = QPushButton("Купить")
        buy_btn.clicked.connect(lambda: self._make_trade("crypto", "buy"))
        sell_btn = QPushButton("Продать")
        sell_btn.clicked.connect(lambda: self._make_trade("crypto", "sell"))
        btn_row.addWidget(buy_btn)
        btn_row.addWidget(sell_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return widget

    def _build_portfolio_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info_row = QHBoxLayout()
        self.lbl_total = QLabel("Стоимость: 0.00")
        self.lbl_cash = QLabel("Кэш: 0.00")
        self.lbl_pnl = QLabel("PnL: 0.00")
        for lbl in (self.lbl_total, self.lbl_cash, self.lbl_pnl):
            lbl.setStyleSheet("padding: 6px; font-weight: bold;")
            info_row.addWidget(lbl)
        info_row.addStretch()
        layout.addLayout(info_row)

        layout.addWidget(QLabel("Активы:"))
        self.holdings_table = QTableWidget(0, 4)
        self.holdings_table.setHorizontalHeaderLabels(
            ["Актив", "Количество", "Средняя цена", "Текущая стоимость"]
        )
        self.holdings_table.verticalHeader().setVisible(False)
        self.holdings_table.setAlternatingRowColors(True)
        self.holdings_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.holdings_table)

        layout.addWidget(QLabel("История сделок:"))
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            ["Время", "Актив", "Тип", "Кол-во", "Цена"]
        )
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.history_table, stretch=1)

        btn_row = QHBoxLayout()
        snapshot_btn = QPushButton("Сохранить снимок")
        snapshot_btn.clicked.connect(self._save_snapshot)
        export_btn = QPushButton("Экспорт CSV")
        export_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(snapshot_btn)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return widget

    def _build_status_bar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_updated = QLabel("Обновлено: —")
        self.lbl_balance = QLabel("Баланс: 0.00")
        self.status.addPermanentWidget(self.lbl_updated)
        self.status.addPermanentWidget(self.lbl_balance)
        self._tick_clock()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background-color: #f5f5f5; }
            QTabWidget::pane { border: 1px solid #c4c4c4; background: #ffffff; }
            QTabBar::tab {
                background: #e8e8e8;
                padding: 10px 40px;
                min-width: 120px;
                min-height: 18px;
                margin-right: 2px;
                border: 1px solid #c4c4c4;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1976d2;
                font-weight: bold;
                margin-bottom: -1px;
            }
            QTabBar::tab:hover:!selected { background: #d8d8d8; }
            QTableWidget {
                gridline-color: #e0e0e0;
                background: #ffffff;
                alternate-background-color: #fafafa;
            }
            QHeaderView::section {
                background: #f0f0f0;
                padding: 8px;
                border: 1px solid #c4c4c4;
                font-weight: bold;
            }
            QStatusBar {
                background: #f0f0f0;
                border-top: 1px solid #c4c4c4;
                color: #555555;
            }
            QPushButton {
                padding: 6px 14px;
                border: 1px solid #1976d2;
                border-radius: 4px;
                background: #1976d2;
                color: white;
            }
            QPushButton:hover { background: #1565c0; }
            """
        )

    def _refresh_all(self) -> None:
        self.service.fetch_all()

    def _on_rates_ready(self, cbr_data: dict, crypto_data: dict, crypto_meta: list) -> None:
        self.cbr_prices = cbr_data
        self.crypto_prices = crypto_data
        if crypto_meta:
            self.crypto_meta = crypto_meta
        self.last_update = datetime.now()
        self._fill_cbr_table()
        self._fill_crypto_table()
        self._fill_history_table()
        self._check_sl_tp()
        self._update_portfolio_view()

    def _on_service_error(self, message: str) -> None:
        self.status.showMessage(f"Ошибка: {message}", 5000)

    def _on_history_ready(self, asset: str, data: list, kind: str, display_name: str) -> None:
        rate = self._usd_rate() or 1.0
        prices = [float(row.get("close") or row.get("value") or 0) for row in data]
        if kind == "crypto":
            prices = [p * rate for p in prices]
        dates = [str(row.get("date", "")) for row in data]
        if kind == "cbr":
            self.cbr_chart.set_data(prices, dates, display_name)
        else:
            self.crypto_chart.set_data(prices, dates, display_name)

    def _usd_rate(self) -> float:
        usd_info = self.cbr_prices.get("USD")
        if usd_info is None:
            return 0.0
        nominal = usd_info.get("nominal") or 1
        return usd_info["value"] / nominal

    def _fill_cbr_table(self) -> None:
        rows = []
        for code in CBR_CODES_20:
            info = self.cbr_prices.get(code)
            if info is None:
                continue
            rows.append((
                code, info["name"], info["value"], info["nominal"],
                info["value"] / info["nominal"],
            ))
        self.cbr_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                text = f"{val:.4f}" if isinstance(val, float) else str(val)
                self.cbr_table.setItem(i, j, QTableWidgetItem(text))

    def _fill_crypto_table(self) -> None:
        rate = self._usd_rate()
        rows = []
        for cid, meta in self.crypto_meta:
            info = self.crypto_prices.get(cid)
            if info is None:
                continue
            rows.append((
                cid, meta.get("symbol", ""), meta.get("name", ""),
                info["price_usd"] * rate,
                info["percent_change_1h"], info["percent_change_24h"],
            ))
        self.crypto_table.setRowCount(len(rows))
        for i, (cid, symbol, name, price, p1, p24) in enumerate(rows):
            symbol_item = QTableWidgetItem(symbol)
            symbol_item.setData(Qt.UserRole, cid)
            symbol_item.setTextAlignment(Qt.AlignCenter)
            self.crypto_table.setItem(i, 0, symbol_item)
            self.crypto_table.setItem(i, 1, QTableWidgetItem(name))
            self.crypto_table.setItem(i, 2, QTableWidgetItem(f"{price:,.2f}".replace(",", " ")))
            for col, val in ((3, p1), (4, p24)):
                item = QTableWidgetItem(f"{val:+.2f}")
                item.setForeground(QColor("green") if val >= 0 else QColor("red"))
                item.setTextAlignment(Qt.AlignCenter)
                self.crypto_table.setItem(i, col, item)

    def _fill_history_table(self) -> None:
        history = self.db.get_history(limit=50)
        self.history_table.setRowCount(len(history))
        for i, row in enumerate(history):
            for j, key in enumerate(["timestamp", "asset", "type", "amount", "price"]):
                val = row.get(key, "")
                text = f"{val:.4f}" if isinstance(val, float) else str(val)
                self.history_table.setItem(i, j, QTableWidgetItem(text))

    def _on_cbr_row_clicked(self, row: int, _col: int) -> None:
        self.selected_row_cbr = row
        item = self.cbr_table.item(row, 0)
        if item is None:
            return
        code = item.text()
        self.service.fetch_history("cbr", CBR_HISTORY_IDS.get(code, code), code)

    def _on_crypto_row_clicked(self, row: int, _col: int) -> None:
        self.selected_row_crypto = row
        item = self.crypto_table.item(row, 0)
        if item is None:
            return
        symbol = item.text()
        cid = item.data(Qt.UserRole)
        self.service.fetch_history("crypto", str(cid), symbol)

    def _make_trade(self, market: str, side: str) -> None:
        if market == "cbr":
            row = self.selected_row_cbr
            table = self.cbr_table
            price_col = 4
            asset = None
        else:
            row = self.selected_row_crypto
            table = self.crypto_table
            price_col = 2
            asset = None

        if row < 0 or table.item(row, 0) is None:
            QMessageBox.warning(self, "Trading Sandbox", "Сначала выбери актив в таблице")
            return

        if market == "cbr":
            asset = table.item(row, 0).text()
        else:
            symbol_item = table.item(row, 0)
            asset = symbol_item.text()

        try:
            price = float(table.item(row, price_col).text().replace(" ", ""))
        except (ValueError, AttributeError):
            QMessageBox.warning(self, "Trading Sandbox", "Нет цены для этого актива")
            return

        amount, ok = QInputDialog.getDouble(
            self, "Trading Sandbox", f"Количество {asset}:", 1.0, 0.0, 1_000_000.0, 6
        )
        if not ok:
            return

        stop_loss = take_profit = None
        if side == "buy":
            sl_text = f"Стоп-лосс для {asset}\n(0 — без стоп-лосса):"
            sl, ok = QInputDialog.getDouble(
                self, "Стоп-лосс", sl_text, price * 0.95, 0.0, price, 4
            )
            if not ok:
                return
            stop_loss = sl if sl > 0 else None

            tp_text = f"Тейк-профит для {asset}\n(0 — без тейк-профита):"
            tp, ok = QInputDialog.getDouble(
                self, "Тейк-профит", tp_text, price * 1.10, 0.0, 1e9, 4
            )
            if not ok:
                return
            take_profit = tp if tp > 0 else None

        try:
            if side == "buy":
                self.portfolio.buy(asset, amount, price)
            else:
                self.portfolio.sell(asset, amount, price)
        except ValueError as e:
            QMessageBox.warning(self, "Trading Sandbox", str(e))
            return

        self.db.save_transaction(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            asset=asset, type_=market, side=side,
            amount=amount, price=price, total=amount * price,
        )

        if side == "buy" and (stop_loss or take_profit):
            order = Order(
                asset=asset, order_type=market, side=side,
                amount=amount, price=price,
                stop_loss=stop_loss, take_profit=take_profit,
            )
            self.engine.add_order(order)
            self.db.save_order(
                asset=asset, type_=market, side=side, amount=amount,
                price=price, stop_loss=stop_loss, take_profit=take_profit,
                status="active",
            )

        self._update_portfolio_view()
        self._fill_history_table()
        self.status.showMessage(
            f"{'Куплено' if side == 'buy' else 'Продано'} {amount} {asset} @ {price:.4f}",
            4000,
        )

    def _check_sl_tp(self) -> None:
        prices = self._flat_prices()
        triggered = self.engine.update_prices(prices)
        for order in triggered:
            try:
                self.portfolio.sell(order.asset, order.amount, prices[order.asset])
            except ValueError:
                pass
            self.db.save_transaction(
                timestamp=datetime.now().isoformat(timespec="seconds"),
                asset=order.asset, type_="sl_tp", side="sell",
                amount=order.amount, price=prices[order.asset],
                total=order.amount * prices[order.asset],
            )
            self.status.showMessage(
                f"SL/TP сработал: {order.asset} @ {prices[order.asset]:.4f}",
                5000,
            )

    def _update_portfolio_view(self) -> None:
        prices = self._flat_prices()
        total = self.portfolio.get_total_value(prices)
        cash = self.portfolio.balance_usd
        pnl = self.portfolio.get_pnl(prices)

        self.lbl_total.setText(f"Стоимость: {total:.2f}")
        self.lbl_cash.setText(f"Кэш: {cash:.2f}")
        self.lbl_pnl.setText(f"PnL: {pnl:+.2f}")
        self.lbl_pnl.setStyleSheet(
            "padding: 6px; font-weight: bold; color: "
            + ("green" if pnl >= 0 else "red") + ";"
        )
        self.lbl_balance.setText(f"Баланс: {cash:.2f}")

        rows = [
            (asset, h["amount"], h["avg_price"],
             h["amount"] * prices.get(asset, h["avg_price"]))
            for asset, h in self.portfolio.holdings.items()
        ]
        self.holdings_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                text = f"{val:.4f}" if isinstance(val, float) else str(val)
                self.holdings_table.setItem(i, j, QTableWidgetItem(text))

    def _flat_prices(self) -> dict:
        rate = self._usd_rate() or 1.0
        out = {}
        for code, info in self.cbr_prices.items():
            nominal = info.get("nominal") or 1
            out[code] = info["value"] / nominal
        for cid, info in self.crypto_prices.items():
            symbol = next(
                (m.get("symbol") for c, m in self.crypto_meta if c == cid), cid,
            )
            out[symbol] = info["price_usd"] * rate
        return out

    def _save_snapshot(self) -> None:
        prices = self._flat_prices()
        total = self.portfolio.get_total_value(prices)
        assets_value = total - self.portfolio.balance_usd
        self.db.save_snapshot(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            total_value=total,
            cash=self.portfolio.balance_usd,
            assets_value=assets_value,
        )
        self.status.showMessage("Снимок портфеля сохранён", 3000)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт CSV", "transactions.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            self.db.export_to_csv("transactions", path)
            self.status.showMessage(f"Экспортировано в {path}", 5000)
        except (OSError, sqlite3.Error) as e:
            QMessageBox.warning(self, "Trading Sandbox", f"Не удалось экспортировать: {e}")

    def _tick_clock(self) -> None:
        if self.last_update is None:
            self.lbl_updated.setText("Обновлено: —")
        else:
            self.lbl_updated.setText(
                f"Обновлено: {self.last_update:%H:%M:%S}"
            )
