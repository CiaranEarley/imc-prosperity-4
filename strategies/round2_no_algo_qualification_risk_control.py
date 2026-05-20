from datamodel import TradingState


class Trader:
    """Round 2 public strategy file.

    This intentionally returns no algorithmic orders. After the Round 1 result,
    the correct tournament decision was to avoid algorithmic risk and use the
    manual allocation to guarantee qualification for the finals.
    """

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}
        return result, 0, state.traderData or ""
