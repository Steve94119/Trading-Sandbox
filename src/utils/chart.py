from datetime import datetime

import pyqtgraph as pg
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from config import DATE_FORMATS


pg.setConfigOption("background", "#ffffff")
pg.setConfigOption("foreground", "#222222")


def _parse_timestamp(value) -> float:
    if not value:
        return 0.0
    text = str(value)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    return 0.0


class PriceChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout_widget = pg.GraphicsLayoutWidget()
        layout_widget.setParent(self)

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(layout_widget)

        self.plot = layout_widget.addPlot(row=0, col=0)
        self.plot.setTitle("График", color="#1976d2", size="11pt")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.curve = self.plot.plot(pen=pg.mkPen(color="#1976d2", width=2))

    def set_data(self, prices: list, dates: list, title: str) -> None:
        self.plot.clear()
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setTitle(title, color="#1976d2", size="11pt")

        pen = pg.mkPen(color="#1976d2", width=2)

        if dates and len(dates) == len(prices):
            timestamps = [_parse_timestamp(d) for d in dates]
            if any(t > 0 for t in timestamps):
                self.plot.setAxisItems({"bottom": pg.DateAxisItem(orientation="bottom")})
                self.curve = self.plot.plot(timestamps, prices, pen=pen)
                self.plot.setLabel("bottom", "Дата")
                return

        self.curve = self.plot.plot(list(range(len(prices))), prices, pen=pen)
        self.plot.setLabel("bottom", "")