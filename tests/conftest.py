"""Pytest configuration and shared fixtures."""

import pytest
import os
from unittest.mock import Mock, patch

# Try to import pytest-asyncio, fall back to anyio if available
try:
    import pytest_asyncio
    pytest_asyncio_available = True
except ImportError:
    pytest_asyncio_available = False
    try:
        import anyio
        anyio_available = True
    except ImportError:
        anyio_available = False


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "asyncio: marks tests as async tests"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically skip integration tests if not explicitly requested."""
    if config.getoption("-m") and "integration" in config.getoption("-m"):
        # Integration tests are explicitly requested, don't skip
        return
    
    # Skip integration tests by default
    skip_integration = pytest.mark.skip(reason="Integration tests skipped by default. Run with -m integration to enable.")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)

