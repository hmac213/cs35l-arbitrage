"""Custom exceptions for the data engine."""


class EngineError(Exception):
    """Base exception for engine-related errors."""
    pass


class MarketValidationError(EngineError):
    """Exception raised when market data validation fails."""
    pass


class SyncError(EngineError):
    """Exception raised when market synchronization fails."""
    pass


class PollingError(EngineError):
    """Exception raised when market polling fails."""
    pass

