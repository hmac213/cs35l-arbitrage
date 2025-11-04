"""Pytest configuration and shared fixtures."""

import pytest
import os
from unittest.mock import Mock, patch


@pytest.fixture(scope="session")
def dome_api_key():
    """Get Dome API key from environment or use test key."""
    return os.getenv("DOME_API_KEY", "test_api_key")


@pytest.fixture(scope="session")
def dome_base_url():
    """Get Dome API base URL from environment or use default."""
    return os.getenv("DOME_BASE_URL", "http://api.domeapi.io")

