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
    # Use optimized single-query method
    result = db_client.get_paired_markets_enriched()
    
    # Convert datetime strings to ISO format for consistency
    for pair_data in result:
        # Convert market timestamps
        for market_key in ["market_1", "market_2"]:
            market = pair_data[market_key]
            if market.get("resolve_date"):
                market["resolve_date"] = market["resolve_date"] if isinstance(market["resolve_date"], str) else market["resolve_date"].isoformat()
            if market.get("resolve_time"):
                market["resolve_time"] = market["resolve_time"] if isinstance(market["resolve_time"], str) else market["resolve_time"].isoformat()
            if market.get("last_polled_at"):
                market["last_polled_at"] = market["last_polled_at"] if isinstance(market["last_polled_at"], str) else market["last_polled_at"].isoformat()
            if market.get("created_at"):
                market["created_at"] = market["created_at"] if isinstance(market["created_at"], str) else market["created_at"].isoformat()
            if market.get("updated_at"):
                market["updated_at"] = market["updated_at"] if isinstance(market["updated_at"], str) else market["updated_at"].isoformat()
        
        # Convert pair timestamps
        if pair_data.get("created_at"):
            pair_data["created_at"] = pair_data["created_at"] if isinstance(pair_data["created_at"], str) else pair_data["created_at"].isoformat()
        if pair_data.get("updated_at"):
            pair_data["updated_at"] = pair_data["updated_at"] if isinstance(pair_data["updated_at"], str) else pair_data["updated_at"].isoformat()
        
        # Convert orderbook timestamps
        for orderbook_key in ["orderbook_1", "orderbook_2"]:
            orderbook = pair_data.get(orderbook_key)
            if orderbook:
                if orderbook.get("timestamp"):
                    orderbook["timestamp"] = orderbook["timestamp"] if isinstance(orderbook["timestamp"], str) else orderbook["timestamp"].isoformat()
                if orderbook.get("created_at"):
                    orderbook["created_at"] = orderbook["created_at"] if isinstance(orderbook["created_at"], str) else orderbook["created_at"].isoformat()
        
        # Convert opportunity timestamps
        if pair_data.get("current_opportunity"):
            opp = pair_data["current_opportunity"]
            if opp.get("timestamp"):
                opp["timestamp"] = opp["timestamp"] if isinstance(opp["timestamp"], str) else opp["timestamp"].isoformat()
            if opp.get("created_at"):
                opp["created_at"] = opp["created_at"] if isinstance(opp["created_at"], str) else opp["created_at"].isoformat()
        
        # Convert last_opportunity_time
        if pair_data.get("last_opportunity_time"):
            pair_data["last_opportunity_time"] = pair_data["last_opportunity_time"] if isinstance(pair_data["last_opportunity_time"], str) else pair_data["last_opportunity_time"].isoformat()
    
    return result

