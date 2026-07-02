import sqlite3
from datetime import datetime, timedelta

from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
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

from config import (
    CBR_CODES_20,
    CBR_HISTORY_DAYS,
    CBR_HISTORY_IDS,
    CHART_HISTORY_DAYS,
    CLOCK_TICK_MS,
    CRYPTO_LIMIT,
    DB_HISTORY_LIMIT,
    DEFAULT_CRYPTO_IDS,
    FALLBACK_CRYPTO,
    REFRESH_INTERVAL_MS,
    START_BALANCE,
)
from src.api import cbr_api, crypto_api
from src.models import Order, TradingEngine, VirtualPortfolio
from src.utils import DatabaseManager, PriceChart


class RatesService(QObject):
    rates_ready = pyqtSignal(dict, dict, list)
    error = pyqtSignal(str)
    history_ready = pyqtSignal(str, list, str, str)

    def __init__(self) -> None:
        super().__init__()
        self.crypto_ids: list[str] = list(DEFAULT_CRYPTO_IDS)

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
            self.crypto_ids = [m["id"] for m in FALLBACK_CRYPTO]
            meta = list(FALLBACK_CRYPTO)

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
                    asset,
                    (today - timedelta(days=CBR_HISTORY_DAYS)).strftime("%d/%m/%Y"),
                    today.strftime("%d/%m/%Y"),
                )
            else:
                data = crypto_api.get_crypto_history(asset, days=CHART_HISTORY_DAYS)
        except RuntimeError as e:
            self.error.emit(str(e))
            data = []

        self.history_ready.emit(asset, data, kind, display_name)


def _format_cell(value) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Trading Sandbox")
        self.resize(1100, 700)

        self.portfolio = VirtualPortfolio(START_BALANCE)
        self.engine = TradingEngine(self.portfolio)
        self.db = DatabaseManager()
        self.service = RatesService()
        self.service.rates_ready.connect(self._on_rates_ready)
        self.service.history_ready.connect(self._on_history_ready)
        self.service.error.connect(self._on_service_error)

        self.cbr_prices: dict = {}
        self.crypto_prices: dict = {}
        self.crypto_meta: list = []
        self.last_update = None
        self.selected_row_cbr = -1
        self.selected_row_crypto = -1

        self._build_menu()
        self._build_tabs()
        self._build_status_bar()
        self._apply_style()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick_clock)
        self.clock_timer.start(CLOCK_TICK_MS)

        QtCore.QTimer.singleShot(0, self._refresh_all)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        export_action = QAction("Экспорт CSV", self)
        export_action.triggered.connect(self._export_csv)
        file_menu.addAction(export_action)
        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _build_tabs(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_currencies_tab(), "Валюты")
        tabs.addTab(self._build_crypto_tab(), "Криптовалюты")
        tabs.addTab(self._build_portfolio_tab(), "Портфель")
        self.setCentralWidget(tabs)

    def _build_market_tab(self, table_attr: str, headers: list[str], chart_title_hint: str):
        def build():
            widget = QWidget()
            layout = QVBoxLayout(widget)

            table = QTableWidget(0, len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            layout.addWidget(table)
            setattr(self, table_attr, table)

            chart = PriceChart()
            chart.plot.setTitle(chart_title_hint, color="#888", size="10pt")
            layout.addWidget(chart, stretch=1)
            # сохранить ссылку на график
            if table_attr == "cbr_table":
                self.cbr_chart = chart
            else:
                self.crypto_chart = chart

            btn_row = QHBoxLayout()
            market_code = "cbr" if table_attr == "cbr_table" else "crypto"
            for label, side in (("Купить", "buy"), ("Продать", "sell")):
                btn = QPushButton(label)
                btn.clicked.connect(lambda _=False, m=market_code, s=side: self._make_trade(m, s))
                btn_row.addWidget(btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

            return widget
        return build

    def _build_currencies_tab(self) -> QWidget:
        builder = self._build_market_tab(
            "cbr_table",
            ["Код", "Название", "Цена (RUB)", "Номинал", "Курс за 1"],
            "Выбери валюту, кликнув по строке",
        )
        widget = builder()
        self.cbr_table.cellClicked.connect(self._on_cbr_row_clicked)
        return widget

    def _build_crypto_tab(self) -> QWidget:
        builder = self._build_market_tab(
            "crypto_table",
            ["Тикер", "Название", "Цена (RUB)", "1ч %", "24ч %"],
            "Выбери монету, кликнув по строке",
        )
        widget = builder()
        self.crypto_table.cellClicked.connect(self._on_crypto_row_clicked)
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
        chart = self.cbr_chart if kind == "cbr" else self.crypto_chart
        chart.set_data(prices, dates, display_name)

    def _usd_rate(self) -> float:
        info = self.cbr_prices.get("USD")
        if info is None:
            return 0.0
        return info["value"] / (info.get("nominal") or 1)

    def _fill_cbr_table(self) -> None:
        rows = [
            (code, info["name"], info["value"], info["nominal"],
             info["value"] / info["nominal"])
            for code in CBR_CODES_20
            if (info := self.cbr_prices.get(code)) is not None
        ]
        self.cbr_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.cbr_table.setItem(i, j, QTableWidgetItem(_format_cell(val)))

    def _fill_crypto_table(self) -> None:
        rate = self._usd_rate()
        rows = []
        for cid, meta in self.crypto_meta:
            info = self.crypto_prices.get(cid)
            if info is None:
                continue
            rows.append((
                cid,
                meta.get("symbol", ""),
                meta.get("name", ""),
                info["price_usd"] * rate,
                info["percent_change_1h"],
                info["percent_change_24h"],
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
        history = self.db.get_history(DB_HISTORY_LIMIT)
        self.history_table.setRowCount(len(history))
        for i, row in enumerate(history):
            for j, key in enumerate(["timestamp", "asset", "type", "amount", "price"]):
                self.history_table.setItem(i, j, QTableWidgetItem(_format_cell(row.get(key, ""))))

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
        cid = item.data(Qt.UserRole)
        self.service.fetch_history("crypto", str(cid), item.text())

    def _make_trade(self, market: str, side: str) -> None:
        if market == "cbr":
            row, table, price_col = self.selected_row_cbr, self.cbr_table, 4
        else:
            row, table, price_col = self.selected_row_crypto, self.crypto_table, 2

        if row < 0 or table.item(row, 0) is None:
            QMessageBox.warning(self, "Trading Sandbox", "Сначала выбери актив в таблице")
            return

        asset = table.item(row, 0).text()
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
            sl, ok = QInputDialog.getDouble(
                self, "Стоп-лосс",
                f"Стоп-лосс для {asset}\n(0 — без стоп-лосса):",
                price * 0.95, 0.0, price, 4,
            )
            if not ok:
                return
            stop_loss = sl if sl > 0 else None

            tp, ok = QInputDialog.getDouble(
                self, "Тейк-профит",
                f"Тейк-профит для {asset}\n(0 — без тейк-профита):",
                price * 1.10, 0.0, 1e9, 4,
            )
            if not ok:
                return
            take_profit = tp if tp > 0 else None

        try:
            (self.portfolio.buy if side == "buy" else self.portfolio.sell)(
                asset, amount, price
            )
        except ValueError as e:
            QMessageBox.warning(self, "Trading Sandbox", str(e))
            return

        now = datetime.now().isoformat(timespec="seconds")
        self.db.save_transaction(
            timestamp=now, asset=asset, type_=market, side=side,
            amount=amount, price=price, total=amount * price,
        )

        if side == "buy" and (stop_loss or take_profit):
            self.engine.add_order(Order(
                asset=asset, market=market, side=side,
                amount=amount, price=price,
                stop_loss=stop_loss, take_profit=take_profit,
            ))
            self.db.save_order(
                asset=asset, type_=market, side=side, amount=amount,
                price=price, stop_loss=stop_loss, take_profit=take_profit,
                status="active",
            )

        self._update_portfolio_view()
        self._fill_history_table()
        verb = "Куплено" if side == "buy" else "Продано"
        self.status.showMessage(f"{verb} {amount} {asset} @ {price:.4f}", 4000)

    def _check_sl_tp(self) -> None:
        prices = self._flat_prices()
        for order in self.engine.update_prices(prices):
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
        cash = self.portfolio.balance_usd
        total = self.portfolio.get_total_value(prices)
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
            (asset, h["amount"], h["avg_price"], h["amount"] * prices.get(asset, h["avg_price"]))
            for asset, h in self.portfolio.holdings.items()
        ]
        self.holdings_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.holdings_table.setItem(i, j, QTableWidgetItem(_format_cell(val)))

    def _flat_prices(self) -> dict:
        rate = self._usd_rate() or 1.0
        out = {}
        for code, info in self.cbr_prices.items():
            out[code] = info["value"] / (info.get("nominal") or 1)
        for cid, info in self.crypto_prices.items():
            symbol = next((m.get("symbol") for c, m in self.crypto_meta if c == cid), cid)
            out[symbol] = info["price_usd"] * rate
        return out

    def _save_snapshot(self) -> None:
        prices = self._flat_prices()
        total = self.portfolio.get_total_value(prices)
        self.db.save_snapshot(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            total_value=total,
            cash=self.portfolio.balance_usd,
            assets_value=total - self.portfolio.balance_usd,
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
            self.lbl_updated.setText(f"Обновлено: {self.last_update:%H:%M:%S}")