from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List


@dataclass
class PaperOrder:
    id: str
    symbol: str
    side: str
    qty: float
    avg_price: float
    created_at: datetime
    status: str = "filled"


class PaperBroker:

    def __init__(self):
        self.cash = 100_000.0
        self.positions: Dict[str, Dict] = {}
        self.order_history: List[dict] = []

    # --------------------------------------------------------
    # Submit Order
    # --------------------------------------------------------

    def submit_order(self, symbol: str, side: str, qty: float, price: float):

        symbol = symbol.upper()
        qty = float(qty)
        price = float(price)

        if side == "buy":

            cost = qty * price

            if cost > self.cash:
                raise ValueError("Not enough cash")

            self.cash -= cost

            pos = self.positions.get(symbol)

            if pos:
                total_qty = pos["qty"] + qty
                new_avg = ((pos["avg_price"] * pos["qty"]) + (price * qty)) / total_qty

                pos["qty"] = total_qty
                pos["avg_price"] = new_avg
            else:
                self.positions[symbol] = {
                    "symbol": symbol,
                    "qty": qty,
                    "avg_price": price
                }

        elif side == "sell":

            pos = self.positions.get(symbol)

            if not pos or pos["qty"] < qty:
                raise ValueError("Not enough shares")

            proceeds = qty * price
            self.cash += proceeds

            pos["qty"] -= qty

            if pos["qty"] <= 0:
                del self.positions[symbol]

        order = PaperOrder(
            id=str(len(self.order_history) + 1),
            symbol=symbol,
            side=side,
            qty=qty,
            avg_price=price,
            created_at=datetime.utcnow(),
        )

        self.order_history.append({
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "created_at": order.created_at.isoformat()
        })

        return order

    # --------------------------------------------------------
    # Live Positions (THIS FIXES YOUR PNL)
    # --------------------------------------------------------

    def list_positions(self, price_lookup):

        results = []

        for symbol, pos in self.positions.items():

            qty = float(pos["qty"])
            avg_price = float(pos["avg_price"])

            # THIS MUST COME FROM MARKET FEED
            market_price = float(price_lookup(symbol))

            market_value = qty * market_price

            unrealized_pnl = (market_price - avg_price) * qty

            results.append({
                "symbol": symbol,
                "qty": qty,
                "avg_price": round(avg_price, 4),
                "market_price": round(market_price, 4),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
            })

        return results

    # --------------------------------------------------------
    # Orders
    # --------------------------------------------------------

    def list_orders(self):
        return self.order_history