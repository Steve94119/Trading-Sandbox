from datetime import datetime

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QAction,
    QMainWindow,
    QStatusBar,
    QTableWidget,
    QTabWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Trading Sandbox")
        self.resize(900, 600)

        self._build_menu()
        self._build_central_widget()
        self._build_status_bar()
        self._apply_style()
        self._update_status_time()

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Файл")
        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        menu_bar.addMenu("Настройки")

    def _build_central_widget(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._create_table_tab(), "Валюты")
        tabs.addTab(self._create_table_tab(), "Криптовалюты")
        tabs.addTab(self._create_table_tab(), "Портфель")
        self.setCentralWidget(tabs)

    def _create_table_tab(self) -> QTableWidget:
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Название", "Цена", "Изменение %"])
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _build_status_bar(self) -> None:
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_status_time)
        self._timer.start(1000)

    def _update_status_time(self) -> None:
        self._status.showMessage(f"Обновлено: {datetime.now():%Y-%m-%d %H:%M:%S}")

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #c4c4c4;
                background: #ffffff;
            }
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
            QTabBar::tab:hover:!selected {
                background: #d8d8d8;
            }
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
            """
        )
