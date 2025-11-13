"""Arbitrage calculator for finding opportunities between market pairs."""

import logging
from typing import Optional, Tuple
from db.models import OrderbookSnapshot, ArbitrageOpportunity
from .config import EngineConfig

logger = logging.getLogger(__name__)


class ArbitrageCalculator:
    """Calculates arbitrage opportunities from orderbook pairs."""
    
    def __init__(self, fees: Optional[float] = None, min_profit: Optional[float] = None):
        """Initialize the arbitrage calculator.
        
        Args:
            fees: Trading fees as a percentage (e.g., 0.02 for 2%). If None, uses config.
            min_profit: Minimum profit per share to consider. If None, uses config.
        """
        self.fees = fees if fees is not None else EngineConfig.ARBITRAGE_FEES
        self.min_profit = min_profit if min_profit is not None else EngineConfig.ARBITRAGE_MIN_PROFIT
    
    def calculate_arbitrage(
        self,
        orderbook1: OrderbookSnapshot,
        orderbook2: OrderbookSnapshot,
        market_pair_id: str
    ) -> Optional[ArbitrageOpportunity]:
        """Calculate arbitrage opportunity between two orderbooks.
        
        Strategy: Buy YES on one exchange and NO on the other (or vice versa).
        If YES_price + NO_price < 1.0, there's an arbitrage opportunity.
        
        Args:
            orderbook1: First orderbook snapshot.
            orderbook2: Second orderbook snapshot.
            market_pair_id: UUID of the market pair.
            
        Returns:
            ArbitrageOpportunity if profitable, None otherwise.
        """
        # Try both directions:
        # 1. Buy YES on exchange1, Buy NO on exchange2
        # 2. Buy NO on exchange1, Buy YES on exchange2
        
        opportunity1 = self._calculate_yes_no_arbitrage(
            orderbook1, orderbook2, market_pair_id,
            yes_exchange=orderbook1.exchange, no_exchange=orderbook2.exchange
        )
        
        opportunity2 = self._calculate_yes_no_arbitrage(
            orderbook2, orderbook1, market_pair_id,
            yes_exchange=orderbook2.exchange, no_exchange=orderbook1.exchange
        )
        
        # Return the better opportunity (higher profit per share)
        if opportunity1 and opportunity2:
            return opportunity1 if opportunity1.profit_per_share >= opportunity2.profit_per_share else opportunity2
        return opportunity1 or opportunity2
    
    def _calculate_yes_no_arbitrage(
        self,
        yes_orderbook: OrderbookSnapshot,
        no_orderbook: OrderbookSnapshot,
        market_pair_id: str,
        yes_exchange: str,
        no_exchange: str
    ) -> Optional[ArbitrageOpportunity]:
        """Calculate arbitrage by buying YES on one exchange and NO on the other.
        
        Strategy: Buy YES at price P_yes and NO at price P_no.
        Total cost per pair = P_yes + P_no
        If total cost < 1.0, profit = 1.0 - (P_yes + P_no) per pair.
        
        Only fills levels that are individually profitable (per-level profitability check).
        
        Args:
            yes_orderbook: Orderbook for the exchange where we buy YES.
            no_orderbook: Orderbook for the exchange where we buy NO.
            market_pair_id: UUID of the market pair.
            yes_exchange: Exchange name for buying YES.
            no_exchange: Exchange name for buying NO.
            
        Returns:
            ArbitrageOpportunity if profitable, None otherwise.
        """
        # Get YES asks (to buy YES) and NO asks (to buy NO)
        yes_asks = yes_orderbook.yes_asks  # Sorted ascending (best ask first)
        no_asks = no_orderbook.no_asks  # Sorted ascending (best ask first)
        
        if not yes_asks or not no_asks:
            return None
        
        # Get best prices
        best_yes_price = yes_asks[0]['price'] if yes_asks else None
        best_no_price = no_asks[0]['price'] if no_asks else None
        
        if best_yes_price is None or best_no_price is None:
            return None
        
        # Check if there's an arbitrage opportunity at best prices (YES + NO < 1.0)
        total_cost = best_yes_price + best_no_price
        cost_with_fees = total_cost * (1.0 + self.fees)
        profit_per_share = 1.0 - cost_with_fees
        
        if profit_per_share <= self.min_profit:
            return None
        
        # Execution prices should be the best ask (lowest ask) - this is the market order price
        execution_yes_price = best_yes_price
        execution_no_price = best_no_price
        
        # Find maximum size by stepping through levels, checking per-level profitability
        max_size = self._find_max_size_per_level(yes_asks, no_asks, self.fees)
        
        if max_size <= 0:
            return None
        
        # Calculate actual total cost for max_size
        yes_total_cost, no_total_cost = self._calculate_total_cost(max_size, yes_asks, no_asks)
        
        if yes_total_cost is None or no_total_cost is None:
            return None
        
        # Calculate average cost per share (what you'd actually pay for max_size)
        total_cost = yes_total_cost + no_total_cost
        cost_per_share = total_cost / max_size if max_size > 0 else float('inf')
        cost_with_fees_avg = cost_per_share * (1.0 + self.fees)
        avg_profit_per_share = 1.0 - cost_with_fees_avg
        
        # Create direction string: "yes_{yes_exchange}_no_{no_exchange}"
        direction = f"yes_{yes_exchange}_no_{no_exchange}"
        
        return ArbitrageOpportunity(
            market_pair_id=market_pair_id,
            direction=direction,
            yes_exchange=yes_exchange,  # Exchange where we buy YES
            no_exchange=no_exchange,  # Exchange where we buy NO
            yes_price=execution_yes_price,  # Best ask price (market order execution price)
            no_price=execution_no_price,  # Best ask price (market order execution price)
            profit_per_share=avg_profit_per_share,  # Profit using average prices for max_size
            max_size=float(max_size),  # Store as float for DB, but calculated as int
            fees=self.fees
        )
    
    def _find_max_size_per_level(
        self,
        yes_asks: list,
        no_asks: list,
        fees: float
    ) -> int:
        """Find maximum size by stepping through levels, checking per-level profitability.
        
        Only fills a level if that level itself is profitable (not just if total average is profitable).
        Handles differently-sized orderbooks at each level.
        
        Args:
            yes_asks: List of {price, quantity} dicts for YES asks, sorted ascending (best ask first).
            no_asks: List of {price, quantity} dicts for NO asks, sorted ascending (best ask first).
            fees: Trading fees as percentage.
            
        Returns:
            Maximum size (integer) that can be arbitraged profitably.
        """
        if not yes_asks or not no_asks:
            return 0
        
        total_filled = 0
        yes_idx = 0
        no_idx = 0
        yes_remaining = 0.0
        no_remaining = 0.0
        
        while yes_idx < len(yes_asks) and no_idx < len(no_asks):
            # Get current level prices and quantities
            if yes_remaining <= 0:
                yes_price = float(yes_asks[yes_idx].get('price', 0))
                yes_qty = float(yes_asks[yes_idx].get('quantity', 0))
                yes_remaining = yes_qty
                yes_idx += 1
            
            if no_remaining <= 0:
                no_price = float(no_asks[no_idx].get('price', 0))
                no_qty = float(no_asks[no_idx].get('quantity', 0))
                no_remaining = no_qty
                no_idx += 1
            
            # Check if this level combination is profitable
            cost_per_share = yes_price + no_price
            cost_with_fees = cost_per_share * (1.0 + fees)
            profit_per_share = 1.0 - cost_with_fees
            
            if profit_per_share <= self.min_profit:
                # This level is not profitable, stop
                break
            
            # Fill the minimum of remaining quantities at this level
            fill_qty = min(yes_remaining, no_remaining)
            total_filled += int(fill_qty)
            yes_remaining -= fill_qty
            no_remaining -= fill_qty
        
        return int(total_filled)
    
    def _calculate_total_cost(
        self,
        size: int,
        yes_asks: list,
        no_asks: list
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate total cost to buy 'size' shares from both orderbooks.
        
        Args:
            size: Number of shares to buy (integer).
            yes_asks: List of {price, quantity} dicts for YES asks, sorted ascending.
            no_asks: List of {price, quantity} dicts for NO asks, sorted ascending.
            
        Returns:
            Tuple of (yes_total_cost, no_total_cost), or (None, None) if can't fill.
        """
        if size <= 0:
            return 0.0, 0.0
        
        yes_cost = 0.0
        no_cost = 0.0
        remaining = float(size)
        
        # Fill YES asks
        for entry in yes_asks:
            if remaining <= 0:
                break
            
            price = float(entry.get('price', 0))
            qty = float(entry.get('quantity', 0))
            
            if qty <= 0:
                continue
            
            fill_qty = min(remaining, qty)
            yes_cost += price * fill_qty
            remaining -= fill_qty
        
        if remaining > 0:
            return None, None  # Can't fill from YES asks
        
        remaining = float(size)
        
        # Fill NO asks
        for entry in no_asks:
            if remaining <= 0:
                break
            
            price = float(entry.get('price', 0))
            qty = float(entry.get('quantity', 0))
            
            if qty <= 0:
                continue
            
            fill_qty = min(remaining, qty)
            no_cost += price * fill_qty
            remaining -= fill_qty
        
        if remaining > 0:
            return None, None  # Can't fill from NO asks
        
        return yes_cost, no_cost
    
    def _estimate_max_size(self, buy_side: list, sell_side: list) -> float:
        """Estimate maximum possible size based on available liquidity.
        
        Args:
            buy_side: List of {price, quantity} dicts.
            sell_side: List of {price, quantity} dicts.
            
        Returns:
            Estimated maximum size.
        """
        buy_liquidity = sum(entry.get('quantity', 0) for entry in buy_side)
        sell_liquidity = sum(entry.get('quantity', 0) for entry in sell_side)
        return min(buy_liquidity, sell_liquidity)
    
    def _calculate_avg_price(
        self,
        side: list,
        size: float,
        is_ask: bool
    ) -> Tuple[Optional[float], float]:
        """Calculate average price for filling a given size.
        
        Args:
            side: List of {price, quantity} dicts.
            size: Size to fill.
            is_ask: True if this is the ask side (buying), False if bid side (selling).
            
        Returns:
            Tuple of (average_price, filled_size). Returns (None, 0) if can't fill.
        """
        if not side or size <= 0:
            return None, 0.0
        
        total_cost = 0.0
        remaining = size
        filled = 0.0
        
        # Iterate through orders
        for entry in side:
            price = entry.get('price', 0)
            quantity = entry.get('quantity', 0)
            
            if quantity <= 0:
                continue
            
            fill_quantity = min(remaining, quantity)
            total_cost += price * fill_quantity
            filled += fill_quantity
            remaining -= fill_quantity
            
            if remaining <= 0:
                break
        
        if filled <= 0:
            return None, 0.0
        
        avg_price = total_cost / filled
        return avg_price, filled

