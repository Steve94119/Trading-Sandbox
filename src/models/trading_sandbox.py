from typing import Optional

from config import START_BALANCE


class VirtualPortfolio:
    def __init__(self, balance_usd: float = START_BALANCE) -> None:
        self.start_balance = balance_usd
        self.balance_usd = balance_usd
        self.holdings: dict[str, dict[str, float]] = {}

    def buy(self, asset: str, amount: float, price: float) -> None:
        cost = amount * price
        if cost > self.balance_usd:
            raise ValueError("Недостаточно средств")

        self.balance_usd -= cost

        holding = self.holdings.get(asset, {"amount": 0.0, "avg_price": 0.0})
        new_amount = holding["amount"] + amount
        new_avg = (holding["amount"] * holding["avg_price"] + cost) / new_amount
        self.holdings[asset] = {"amount": new_amount, "avg_price": new_avg}

    def sell(self, asset: str, amount: float, price: float) -> None:
        holding = self.holdings.get(asset)
        if holding is None or holding["amount"] < amount:
            raise ValueError("Недостаточно актива для продажи")

        self.balance_usd += amount * price
        holding["amount"] -= amount
        if holding["amount"] == 0:
            del self.holdings[asset]

    def get_total_value(self, prices: dict) -> float:
        total = self.balance_usd
        for asset, holding in self.holdings.items():
            price = prices.get(asset, holding["avg_price"])
            total += holding["amount"] * price
        return total

    def get_pnl(self, prices: dict) -> float:
        return self.get_total_value(prices) - self.start_balance


class Order:
    def __init__(
        self,
        asset: str,
        market: str,
        side: str,
        amount: float,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> None:
        self.asset = asset
        self.market = market
        self.side = side
        self.amount = amount
        self.price = price
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def __repr__(self) -> str:
        return (f"Order({self.side} {self.amount} {self.asset} @ {self.price}, "
                f"SL={self.stop_loss}, TP={self.take_profit})")


class TradingEngine:
    def __init__(self, portfolio: VirtualPortfolio) -> None:
        self.portfolio = portfolio
        self.orders: list[Order] = []

    def add_order(self, order: Order) -> None:
        self.orders.append(order)

    def update_prices(self, prices: dict) -> list[Order]:
        triggered: list[Order] = []
        remaining: list[Order] = []

        for order in self.orders:
            price = prices.get(order.asset)
            if price is None:
                remaining.append(order)
                continue

            triggered_sl = order.stop_loss is not None and price <= order.stop_loss
            triggered_tp = order.take_profit is not None and price >= order.take_profit

            if triggered_sl or triggered_tp:
                try:
                    self.portfolio.sell(order.asset, order.amount, price)
                    triggered.append(order)
                except ValueError:
                    pass
            else:
                remaining.append(order)

        self.orders = remaining
        return triggered