"""Market pairs API endpoint."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends
from db.client import SupabaseClient
from db.models import MarketPair, DatabaseMarket, OrderbookSnapshot, ArbitrageOpportunity
from api.dependencies import get_db_client

router = APIRouter()


def _market_to_dict(market: DatabaseMarket) -> Dict[str, Any]:
    """Convert DatabaseMarket to dictionary for JSON response."""
    return {
        "id": market.id,
        "market_id": market.market_id,
        "exchange": market.exchange,
        "name": market.name,
        "rules": market.rules,
        "resolve_date": market.resolve_date.isoformat() if market.resolve_date else None,
        "resolve_time": market.resolve_time.isoformat() if market.resolve_time else None,
        "category": market.category,
        "subcategory": market.subcategory,
        "tags": market.tags,
        "description": market.description,
        "status": market.status,
        "last_polled_at": market.last_polled_at.isoformat() if market.last_polled_at else None,
        "extra": market.extra,
        "created_at": market.created_at.isoformat() if market.created_at else None,
        "updated_at": market.updated_at.isoformat() if market.updated_at else None,
    }


def _orderbook_to_dict(orderbook: Optional[OrderbookSnapshot]) -> Optional[Dict[str, Any]]:
    """Convert OrderbookSnapshot to dictionary for JSON response."""
    if not orderbook:
        return None
    return {
        "yes_bids": orderbook.yes_bids,
        "yes_asks": orderbook.yes_asks,
        "no_bids": orderbook.no_bids,
        "no_asks": orderbook.no_asks,
        "timestamp": orderbook.timestamp.isoformat() if orderbook.timestamp else None,
        "created_at": orderbook.created_at.isoformat() if orderbook.created_at else None,
    }


def _opportunity_to_dict(opportunity: Optional[ArbitrageOpportunity]) -> Optional[Dict[str, Any]]:
    """Convert ArbitrageOpportunity to dictionary for JSON response."""
    if not opportunity:
        return None
    return {
        "direction": opportunity.direction,
        "yes_exchange": opportunity.yes_exchange,
        "no_exchange": opportunity.no_exchange,
        "yes_price": opportunity.yes_price,
        "no_price": opportunity.no_price,
        "profit_per_share": opportunity.profit_per_share,
        "max_size": opportunity.max_size,
        "fees": opportunity.fees,
        "timestamp": opportunity.timestamp.isoformat() if opportunity.timestamp else None,
        "created_at": opportunity.created_at.isoformat() if opportunity.created_at else None,
    }


@router.get(
    "/get_paired_markets",
    summary="Get all market pairs with enriched data",
    description="""
    Returns all market pairs from the database with enriched data including:
    
    - **Pair metadata**: similarity_score, llm_verified, llm_confidence
    - **Market 1 details**: Complete market information for the first market
    - **Market 2 details**: Complete market information for the second market
    - **Latest orderbooks**: Most recent orderbook snapshots for both markets
    - **Current arbitrage opportunity**: Latest calculated arbitrage opportunity (if profitable)
    - **Last opportunity timestamp**: When the most recent opportunity was detected
    
    **Response Format:**
    - Returns an array of MarketPair objects
    - Each pair contains full market details, orderbooks, and opportunity data
    - Fields may be null if data is not available (e.g., no orderbook yet, no opportunity)
    
    **Note:** This endpoint returns all pairs. Filtering should be done on the frontend.
    For detailed API documentation, see API_DOCUMENTATION.md.
    """,
    response_description="Array of market pairs with enriched data",
    tags=["market-pairs"]
)
async def get_paired_markets(
    db_client: SupabaseClient = Depends(get_db_client)
) -> List[Dict[str, Any]]:
    """Get all market pairs with enriched data.
    
    Returns a list of all market pairs, each containing:
    - Pair metadata (id, similarity_score, llm_verified, etc.)
    - Market 1 details
    - Market 2 details
    - Latest orderbook for market 1
    - Latest orderbook for market 2
    - Current arbitrage opportunity (if exists)
    - Last opportunity timestamp
    
    Returns:
        List of enriched market pair dictionaries.
    """
    # Get all market pairs
    pairs = db_client.get_all_market_pairs()
    
    result = []
    
    for pair in pairs:
        # Fetch market 1 details
        market_1 = db_client.get_market_by_id(pair.market_1_id)
        if not market_1:
            continue  # Skip if market not found
        
        # Fetch market 2 details
        market_2 = db_client.get_market_by_id(pair.market_2_id)
        if not market_2:
            continue  # Skip if market not found
        
        # Fetch latest orderbooks
        orderbook_1 = db_client.get_latest_orderbook(
            market_1.market_id,
            market_1.exchange
        )
        orderbook_2 = db_client.get_latest_orderbook(
            market_2.market_id,
            market_2.exchange
        )
        
        # Fetch latest arbitrage opportunity
        latest_opportunity = db_client.get_latest_arbitrage_opportunity(pair.id)
        
        # Build response object
        pair_data = {
            "pair_id": pair.id,
            "similarity_score": pair.similarity_score,
            "llm_verified": pair.llm_verified,
            "llm_confidence": pair.llm_confidence,
            "created_at": pair.created_at.isoformat() if pair.created_at else None,
            "updated_at": pair.updated_at.isoformat() if pair.updated_at else None,
            "market_1": _market_to_dict(market_1),
            "market_2": _market_to_dict(market_2),
            "current_opportunity": _opportunity_to_dict(latest_opportunity),
            "last_opportunity_time": (
                latest_opportunity.timestamp.isoformat() 
                if latest_opportunity and latest_opportunity.timestamp 
                else None
            ),
            "orderbook_1": _orderbook_to_dict(orderbook_1),
            "orderbook_2": _orderbook_to_dict(orderbook_2),
        }
        
        result.append(pair_data)
    
    return result

