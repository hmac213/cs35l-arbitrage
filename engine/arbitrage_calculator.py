"""
Arbitrage Calculator - Identifies risk-free profit opportunities between prediction markets.

In prediction markets, YES and NO contracts for the same event always sum to $1.00
at resolution. This module exploits price differences across exchanges - if we can
buy YES on Exchange A and NO on Exchange B for a combined cost less than $1.00,
the difference is guaranteed profit regardless of outcome.
"""

import logging
from typing import Optional, Tuple
from db.models import OrderbookSnapshot, ArbitrageOpportunity
from .config import EngineConfig

logger = logging.getLogger(__name__)

# Business rule: YES + NO contracts always resolve to exactly $1.00
GUARANTEED_PAYOUT = 1.0


class ArbitrageCalculator:
    """
    Calculates arbitrage opportunities between two prediction market orderbooks.

    Arbitrage exists when: YES_price + NO_price < $1.00 (after accounting for fees)

    Attributes:
        fees: Trading fee as decimal (e.g., 0.02 = 2%)
        min_profit: Minimum profit per share threshold to report an opportunity
    """

    def __init__(self, fees: Optional[float] = None, min_profit: Optional[float] = None):
        """
        Initialize calculator with fee structure and profit threshold.

        Args:
            fees: Trading fees as decimal. Defaults to config value.
            min_profit: Minimum profit per share to consider. Defaults to config value.
        """
        self.fees = fees if fees is not None else EngineConfig.ARBITRAGE_FEES
        self.min_profit = min_profit if min_profit is not None else EngineConfig.ARBITRAGE_MIN_PROFIT

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def calculate_arbitrage(
        self,
        orderbook_a: OrderbookSnapshot,
        orderbook_b: OrderbookSnapshot,
        market_pair_id: str
    ) -> Optional[ArbitrageOpportunity]:
        """
        Find the best arbitrage opportunity between two exchange orderbooks.

        Evaluates both directions and returns the more profitable one:
          - Direction 1: Buy YES on Exchange A, Buy NO on Exchange B
          - Direction 2: Buy YES on Exchange B, Buy NO on Exchange A

        Args:
            orderbook_a: Orderbook snapshot from first exchange
            orderbook_b: Orderbook snapshot from second exchange
            market_pair_id: UUID linking the two equivalent markets

        Returns:
            ArbitrageOpportunity with best profit, or None if no profitable opportunity
        """
        opportunity_a_yes = self._calculate_yes_no_arbitrage(
            yes_orderbook=orderbook_a,
            no_orderbook=orderbook_b,
            market_pair_id=market_pair_id,
            yes_exchange=orderbook_a.exchange,
            no_exchange=orderbook_b.exchange
        )

        opportunity_b_yes = self._calculate_yes_no_arbitrage(
            yes_orderbook=orderbook_b,
            no_orderbook=orderbook_a,
            market_pair_id=market_pair_id,
            yes_exchange=orderbook_b.exchange,
            no_exchange=orderbook_a.exchange
        )

        return self._select_best_opportunity(opportunity_a_yes, opportunity_b_yes)

    # -------------------------------------------------------------------------
    # Private: Core Arbitrage Logic
    # -------------------------------------------------------------------------

    def _select_best_opportunity(
        self,
        opportunity_a: Optional[ArbitrageOpportunity],
        opportunity_b: Optional[ArbitrageOpportunity]
    ) -> Optional[ArbitrageOpportunity]:
        """Return the opportunity with higher profit per share, or None if both are None."""
        if opportunity_a and opportunity_b:
            return opportunity_a if opportunity_a.profit_per_share >= opportunity_b.profit_per_share else opportunity_b
        return opportunity_a or opportunity_b

    def _calculate_yes_no_arbitrage(
        self,
        yes_orderbook: OrderbookSnapshot,
        no_orderbook: OrderbookSnapshot,
        market_pair_id: str,
        yes_exchange: str,
        no_exchange: str
    ) -> Optional[ArbitrageOpportunity]:
        """
        Calculate arbitrage profit for buying YES on one exchange and NO on another.

        Args:
            yes_orderbook: Orderbook from exchange where we buy YES contracts
            no_orderbook: Orderbook from exchange where we buy NO contracts
            market_pair_id: UUID of the market pair
            yes_exchange: Name of exchange for YES purchase
            no_exchange: Name of exchange for NO purchase

        Returns:
            ArbitrageOpportunity if profitable after fees, None otherwise
        """
        yes_asks = yes_orderbook.yes_asks
        no_asks = no_orderbook.no_asks

        # Guard clause: need orderbook data on both sides
        if not yes_asks or not no_asks:
            return None

        # Get best available prices (top of orderbook)
        best_yes_price = yes_asks[0].get('price')
        best_no_price = no_asks[0].get('price')

        if best_yes_price is None or best_no_price is None:
            return None

        # Early exit if not profitable at best prices
        profit_per_share = self._calculate_profit_per_share(best_yes_price, best_no_price)
        if profit_per_share <= self.min_profit:
            return None

        # Find maximum executable size across orderbook levels
        max_executable_size = self._find_max_profitable_size(yes_asks, no_asks)
        if max_executable_size <= 0:
            return None

        # Calculate actual costs for the executable size
        yes_total_cost, no_total_cost = self._calculate_fill_cost(max_executable_size, yes_asks, no_asks)
        if yes_total_cost is None or no_total_cost is None:
            return None

        # Compute average profit across all filled levels
        average_profit = self._calculate_average_profit(yes_total_cost, no_total_cost, max_executable_size)

        return ArbitrageOpportunity(
            market_pair_id=market_pair_id,
            direction=f"yes_{yes_exchange}_no_{no_exchange}",
            yes_exchange=yes_exchange,
            no_exchange=no_exchange,
            yes_price=best_yes_price,
            no_price=best_no_price,
            profit_per_share=average_profit,
            max_size=float(max_executable_size),
            fees=self.fees
        )

    # -------------------------------------------------------------------------
    # Private: Profit Calculations
    # -------------------------------------------------------------------------

    def _calculate_profit_per_share(self, yes_price: float, no_price: float) -> float:
        """
        Calculate profit per share given YES and NO prices.
        Formula: Profit = $1.00 - (YES + NO) × (1 + fees)
        """
        combined_cost = yes_price + no_price
        cost_with_fees = combined_cost * (1.0 + self.fees)
        return GUARANTEED_PAYOUT - cost_with_fees

    def _calculate_average_profit(self, yes_total_cost: float, no_total_cost: float, size: int) -> float:
        """Calculate average profit per share when filling across multiple orderbook levels."""
        average_cost_per_share = (yes_total_cost + no_total_cost) / size
        cost_with_fees = average_cost_per_share * (1.0 + self.fees)
        return GUARANTEED_PAYOUT - cost_with_fees

    # -------------------------------------------------------------------------
    # Private: Orderbook Traversal
    # -------------------------------------------------------------------------

    def _find_max_profitable_size(self, yes_asks: list, no_asks: list) -> int:
        """
        Find maximum fillable size where every price level remains profitable.

        Walks through both orderbooks simultaneously, filling the minimum available
        quantity at each price level, stopping when profitability drops below threshold.

        Returns:
            Maximum number of shares that can be profitably arbitraged
        """
        if not yes_asks or not no_asks:
            return 0

        total_shares_filled = 0
        yes_level_index, no_level_index = 0, 0
        yes_quantity_remaining, no_quantity_remaining = 0.0, 0.0

        while yes_level_index < len(yes_asks) and no_level_index < len(no_asks):
            # Load next YES level if current is exhausted
            if yes_quantity_remaining <= 0:
                yes_price = float(yes_asks[yes_level_index].get('price', 0))
                yes_quantity_remaining = float(yes_asks[yes_level_index].get('quantity', 0))
                yes_level_index += 1

            # Load next NO level if current is exhausted
            if no_quantity_remaining <= 0:
                no_price = float(no_asks[no_level_index].get('price', 0))
                no_quantity_remaining = float(no_asks[no_level_index].get('quantity', 0))
                no_level_index += 1

            # Stop if this price combination is no longer profitable
            level_profit = self._calculate_profit_per_share(yes_price, no_price)
            if level_profit <= self.min_profit:
                break

            # Fill the minimum available quantity at this level
            fill_quantity = min(yes_quantity_remaining, no_quantity_remaining)
            total_shares_filled += int(fill_quantity)
            yes_quantity_remaining -= fill_quantity
            no_quantity_remaining -= fill_quantity

        return int(total_shares_filled)

    def _calculate_fill_cost(
        self,
        target_size: int,
        yes_asks: list,
        no_asks: list
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate total cost to fill target_size shares from both orderbooks.

        Returns:
            Tuple of (yes_cost, no_cost), or (None, None) if insufficient liquidity
        """
        if target_size <= 0:
            return 0.0, 0.0

        yes_cost = self._calculate_side_fill_cost(target_size, yes_asks)
        no_cost = self._calculate_side_fill_cost(target_size, no_asks)

        if yes_cost is None or no_cost is None:
            return None, None
        return yes_cost, no_cost

    def _calculate_side_fill_cost(self, target_size: int, orderbook_side: list) -> Optional[float]:
        """
        Calculate cost to fill target_size shares from one side of the orderbook.

        Walks through price levels, accumulating cost until target is filled.

        Returns:
            Total cost to fill, or None if insufficient liquidity
        """
        total_cost = 0.0
        remaining_to_fill = float(target_size)

        for level in orderbook_side:
            if remaining_to_fill <= 0:
                break

            price = float(level.get('price', 0))
            available_quantity = float(level.get('quantity', 0))

            if available_quantity <= 0:
                continue

            fill_at_level = min(remaining_to_fill, available_quantity)
            total_cost += price * fill_at_level
            remaining_to_fill -= fill_at_level

        # Return None if we couldn't fill the entire target size
        if remaining_to_fill > 0:
            return None
        return total_cost

