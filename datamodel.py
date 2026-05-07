import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


Symbol = str
Product = str
Position = int
UserId = str


class Listing(dict):
    def __init__(self, symbol: Symbol, product: Product, denomination: Product):
        super().__init__(symbol=symbol, product=product, denomination=denomination)
        self.symbol = symbol
        self.product = product
        self.denomination = denomination


@dataclass
class Order:
    symbol: Symbol
    price: int
    quantity: int

    def __repr__(self) -> str:
        return f"({self.symbol}, {self.price}, {self.quantity})"


class OrderDepth:
    def __init__(self):
        self.buy_orders: Dict[int, int] = {}
        self.sell_orders: Dict[int, int] = {}


@dataclass
class Trade:
    symbol: Symbol
    price: float
    quantity: int
    buyer: UserId = ""
    seller: UserId = ""
    timestamp: int = 0

    def __repr__(self) -> str:
        return (
            f"({self.symbol}, {self.buyer} << {self.seller}, "
            f"{self.price}, {self.quantity}, {self.timestamp})"
        )


@dataclass
class ConversionObservation:
    bidPrice: float
    askPrice: float
    transportFees: float
    exportTariff: float
    importTariff: float
    sugarPrice: float = 0.0
    sunlightIndex: float = 0.0


class Observation:
    def __init__(
        self,
        plainValueObservations: Optional[Dict[Product, float]] = None,
        conversionObservations: Optional[Dict[Product, ConversionObservation]] = None,
    ):
        self.plainValueObservations = plainValueObservations or {}
        self.conversionObservations = conversionObservations or {}

    def __repr__(self) -> str:
        return (
            f"(plainValueObservations: {self.plainValueObservations}, "
            f"conversionObservations: {self.conversionObservations})"
        )


class TradingState:
    def __init__(
        self,
        traderData: str,
        timestamp: int,
        listings: Dict[Symbol, Listing],
        order_depths: Dict[Symbol, OrderDepth],
        own_trades: Dict[Symbol, List[Trade]],
        market_trades: Dict[Symbol, List[Trade]],
        position: Dict[Product, Position],
        observations: Observation,
    ):
        self.traderData = traderData
        self.timestamp = timestamp
        self.listings = listings
        self.order_depths = order_depths
        self.own_trades = own_trades
        self.market_trades = market_trades
        self.position = position
        self.observations = observations

    def toJSON(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True)


class ProsperityEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Listing):
            return dict(o)
        if hasattr(o, "__dict__"):
            return o.__dict__
        return json.JSONEncoder.default(self, o)
