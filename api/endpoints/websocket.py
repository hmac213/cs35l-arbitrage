"""WebSocket endpoint for live market pairs updates."""

import asyncio
import json
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from db.client import SupabaseClient
from api.dependencies import get_db_client
from api.endpoints.market_pairs import (
    _market_to_dict,
    _orderbook_to_dict,
    _opportunity_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active WebSocket connections
class ConnectionManager:
    """Manages WebSocket connections and broadcasts updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection.
        
        Note: This method is deprecated. Connection acceptance is now done
        directly in the endpoint handler to ensure it happens first.
        """
        # This method is kept for backwards compatibility but connection
        # acceptance is now done directly in the endpoint
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket client added to manager. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected WebSocket clients."""
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

# Global connection manager instance
manager = ConnectionManager()

# Track if background broadcast task is running
_broadcast_task: asyncio.Task | None = None


async def fetch_market_pairs_data() -> List[Dict[str, Any]]:
    """Fetch market pairs data using the same logic as the REST endpoint.
    
    Returns:
        List of enriched market pair dictionaries.
    """
    try:
        db_client = get_db_client()
        # Use the same optimized method as the REST endpoint
        result = db_client.get_paired_markets_enriched()
        
        # Convert datetime strings to ISO format for consistency (same as REST endpoint)
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
    except Exception as e:
        logger.error(f"Error fetching market pairs data: {e}", exc_info=True)
        return []


async def background_broadcast_task(interval: int = 5):
    """Background task that periodically broadcasts market pairs updates.
    
    Args:
        interval: Seconds between broadcasts (default: 5)
    """
    while True:
        try:
            await asyncio.sleep(interval)
            # Only broadcast if there are active connections
            if manager.active_connections:
                data = await fetch_market_pairs_data()
                message = json.dumps(data)
                await manager.broadcast(message)
                logger.debug(f"Broadcasted {len(data)} market pairs to {len(manager.active_connections)} clients")
        except asyncio.CancelledError:
            logger.info("Background broadcast task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in background broadcast task: {e}", exc_info=True)
            await asyncio.sleep(interval)


@router.websocket("/ws/market_pairs")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live market pairs updates.
    
    Clients connect to this endpoint to receive periodic updates of market pairs data.
    Updates are sent every 5 seconds while clients are connected.
    
    Authentication: If auth is implemented, tokens can be passed via query params or headers.
    Example: ws://localhost:8000/ws/market_pairs?token=<auth_token>
    """
    global _broadcast_task
    
    logger.info(f"WebSocket connection attempt from {websocket.client}")
    
    # Accept connection FIRST - this must happen before anything else
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted")
    except Exception as e:
        logger.error(f"Error accepting WebSocket connection: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass
        return
    
    # Add to connection manager after successful accept
    manager.active_connections.append(websocket)
    logger.info(f"WebSocket client added to manager. Total connections: {len(manager.active_connections)}")
    
    # Start background broadcast task on first connection
    if _broadcast_task is None or _broadcast_task.done():
        _broadcast_task = asyncio.create_task(
            background_broadcast_task(interval=5)
        )
        logger.info("Started WebSocket background broadcast task")
    
    # Send initial data asynchronously (don't block the connection)
    async def send_initial_data():
        try:
            data = await fetch_market_pairs_data()
            message = json.dumps(data)
            await websocket.send_text(message)
            logger.debug(f"Sent initial data: {len(data)} market pairs")
        except Exception as e:
            logger.error(f"Error sending initial data: {e}", exc_info=True)
            # Send error to client (but don't fail the connection)
            try:
                await websocket.send_text(json.dumps({"error": f"Failed to fetch initial data: {str(e)}"}))
            except:
                pass
    
    # Don't await - let it run in background so connection is established immediately
    asyncio.create_task(send_initial_data())
    
    try:
        # Keep connection alive and wait for client messages (ping/pong)
        while True:
            # Wait for any message from client (could be ping or close)
            data = await websocket.receive_text()
            
            # If client sends "ping", respond with "pong"
            if data == "ping":
                await websocket.send_text("pong")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)

