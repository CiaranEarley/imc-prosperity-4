from __future__ import annotations

from dataclasses import dataclass


LOW = 670
HIGH = 920
STEP = 5
SALE = 920


RESERVES = list(range(LOW, HIGH + 1, STEP))
BIDS = list(range(LOW, HIGH))
TICK_BIDS = list(range(LOW, HIGH, STEP))


def captures(bid: int) -> int:
    """Number of reserve-price buckets captured by a strict bid > reserve rule."""
    return sum(reserve < bid for reserve in RESERVES)


def first_bid_profit(bid: int) -> float:
    return captures(bid) * (SALE - bid)


def second_bid_penalty(bid: int, avg_second_bid: float) -> float:
    if bid > avg_second_bid:
        return 1.0
    if bid >= SALE:
        return 0.0
    return ((SALE - avg_second_bid) / (SALE - bid)) ** 3


def second_bid_profit(bid: int, avg_second_bid: float) -> float:
    return captures(bid) * (SALE - bid) * second_bid_penalty(bid, avg_second_bid)


def sequential_profit(first_bid: int, second_bid: int, avg_second_bid: float) -> float:
    """Expected units when each counterparty can trade at most once.

    The first bid captures reserve prices below first_bid. The second bid only
    has a chance on reserve prices that were not already captured.
    """
    first_units = captures(first_bid) * (SALE - first_bid)
    if second_bid <= first_bid:
        return first_units
    second_count = sum(first_bid <= reserve < second_bid for reserve in RESERVES)
    second_units = (
        second_count
        * (SALE - second_bid)
        * second_bid_penalty(second_bid, avg_second_bid)
    )
    return first_units + second_units


def best_bid_pair(avg_second_bid: float, bids: list[int] = BIDS) -> tuple[int, int, float]:
    return max(
        (
            (first_bid, second_bid, sequential_profit(first_bid, second_bid, avg_second_bid))
            for first_bid in bids
            for second_bid in bids
        ),
        key=lambda x: x[2],
    )


def best_first_bid(bids: list[int] = BIDS) -> tuple[int, float]:
    return max(((bid, first_bid_profit(bid)) for bid in bids), key=lambda x: x[1])


def best_second_bid(avg_second_bid: float, bids: list[int] = BIDS) -> tuple[int, float]:
    return max(((bid, second_bid_profit(bid, avg_second_bid)) for bid in bids), key=lambda x: x[1])


@dataclass(frozen=True)
class PopulationScenario:
    name: str
    uninformed_avg_bid: float
    informed_share: float


def informed_fixed_point(scenario: PopulationScenario) -> tuple[float, int, float]:
    """Solve the simple mean-field case where informed teams best-respond to the mean.

    If the uninformed crowd is below the no-penalty optimum, informed teams bid the
    no-penalty optimum and pull the average upward. If the crowd is above it, the
    best response is to stay just above the average, so informed teams cannot pull
    the average down unless almost everyone is informed.
    """
    no_penalty_bid, _ = best_first_bid()
    p = scenario.informed_share
    u = scenario.uninformed_avg_bid

    if u <= no_penalty_bid:
        avg = (1 - p) * u + p * no_penalty_bid
    elif p >= 0.999999:
        avg = no_penalty_bid
    else:
        avg = u

    bid, pnl = best_second_bid(avg)
    return avg, bid, pnl


def main() -> None:
    bid1, pnl1 = best_first_bid()
    tick_bid1, tick_pnl1 = best_first_bid(TICK_BIDS)
    print(f"Best first bid: {bid1}  profit units: {pnl1:.2f}")
    print(f"Best first bid if bids must be multiples of 5: {tick_bid1}  profit units: {tick_pnl1:.2f}")
    print()
    print("Best second bid by realized population average:")
    for avg in [740, 760, 780, 790, 795, 800, 805, 820, 850, 880, 900]:
        bid2, pnl2 = best_second_bid(avg)
        tick_bid2, tick_pnl2 = best_second_bid(avg, TICK_BIDS)
        pair1, pair2, pair_pnl = best_bid_pair(avg)
        tick_pair1, tick_pair2, tick_pair_pnl = best_bid_pair(avg, TICK_BIDS)
        print(
            f"  avg={avg:>3}: bid2={bid2:>3}, profit units={pnl2:8.2f}"
            f" | tick bid2={tick_bid2:>3}, tick profit={tick_pnl2:8.2f}"
            f" | pair=({pair1},{pair2}) {pair_pnl:8.2f}"
            f" | tick pair=({tick_pair1},{tick_pair2}) {tick_pair_pnl:8.2f}"
        )

    print()
    print("Mean-field informed-share scenarios:")
    headers = ("scenario", "uninformed_avg", "informed_share", "final_avg", "our_bid2", "profit_units")
    print(",".join(headers))
    for uninformed_name, uninformed_avg in [
        ("bad_low", 760),
        ("neutral", 795),
        ("bad_high", 820),
        ("very_high", 850),
    ]:
        for share in [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
            scenario = PopulationScenario(uninformed_name, uninformed_avg, share)
            avg, bid2, pnl2 = informed_fixed_point(scenario)
            print(
                f"{uninformed_name},{uninformed_avg},{share:.2f},"
                f"{avg:.2f},{bid2},{pnl2:.2f}"
            )


if __name__ == "__main__":
    main()
