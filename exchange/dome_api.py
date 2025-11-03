"""Dome API client wrapper for external API requests."""

import requests
from typing import Dict, Any, Optional
from datetime import datetime


class DomeAPIError(Exception):
    """Base exception for Dome API errors."""
    pass


class DomeAPIClient:
    """Client for making requests to Dome API.
    
    This client handles authentication, request formatting, and error handling
    for both Kalshi and Polymarket endpoints through Dome API.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "http://api.domeapi.io",
        timeout: int = 30
    ):
        """Initialize the Dome API client.
        
        Args:
            api_key: Your Dome API key for authentication.
            base_url: Base URL for Dome API (default: http://api.domeapi.io).
            timeout: Request timeout in seconds (default: 30).
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        })

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request to Dome API.
        
        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path (e.g., '/polymarket/markets').
            params: Query parameters.
            json_data: JSON body for POST requests.
            
        Returns:
            Dict containing the JSON response.
            
        Raises:
            DomeAPIError: If the request fails.
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            raise DomeAPIError(error_msg) from e
        except requests.exceptions.RequestException as e:
            raise DomeAPIError(f"Request failed: {str(e)}") from e

    def get_kalshi_markets(self, **params) -> Dict[str, Any]:
        """Get all markets from Kalshi via Dome API.
        
        Args:
            **params: Additional query parameters for the request.
            
        Returns:
            Dict containing the API response.
        """
        return self._make_request('GET', '/kalshi/markets', params=params)

    def get_kalshi_orderbook(self, market_id: str) -> Dict[str, Any]:
        """Get orderbook for a Kalshi market via Dome API.
        
        Args:
            market_id: The Kalshi market identifier.
            
        Returns:
            Dict containing the orderbook data.
        """
        return self._make_request('GET', f'/kalshi/markets/{market_id}/orderbook')

    def get_kalshi_market_details(self, market_id: str) -> Dict[str, Any]:
        """Get detailed information for a Kalshi market via Dome API.
        
        Args:
            market_id: The Kalshi market identifier.
            
        Returns:
            Dict containing the market details.
        """
        return self._make_request('GET', f'/kalshi/markets/{market_id}')

    def get_polymarket_markets(self, **params) -> Dict[str, Any]:
        """Get all markets from Polymarket via Dome API.
        
        Args:
            **params: Additional query parameters for the request.
            
        Returns:
            Dict containing the API response.
        """
        return self._make_request('GET', '/polymarket/markets', params=params)

    def get_polymarket_orderbook(self, market_id: str) -> Dict[str, Any]:
        """Get orderbook for a Polymarket market via Dome API.
        
        Args:
            market_id: The Polymarket market identifier (token_id or condition_id).
            
        Returns:
            Dict containing the orderbook data.
        """
        return self._make_request('GET', f'/polymarket/markets/{market_id}/orderbook')

    def get_polymarket_market_details(self, market_id: str) -> Dict[str, Any]:
        """Get detailed information for a Polymarket market via Dome API.
        
        Args:
            market_id: The Polymarket market identifier.
            
        Returns:
            Dict containing the market details.
        """
        return self._make_request('GET', f'/polymarket/markets/{market_id}')

    def get_polymarket_market_price(self, token_id: str, **params) -> Dict[str, Any]:
        """Get market price for a Polymarket token via Dome API.
        
        This endpoint is confirmed from Dome API documentation:
        GET /polymarket/market-price/{token_id}
        
        Args:
            token_id: The Polymarket token identifier.
            **params: Additional query parameters (e.g., at_time for historical data).
            
        Returns:
            Dict containing the price data.
        """
        return self._make_request('GET', f'/polymarket/market-price/{token_id}', params=params)

