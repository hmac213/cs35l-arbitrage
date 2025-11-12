-- Create orderbooks table to store orderbook snapshots
-- Format: yes_bids, yes_asks, no_bids, no_asks as JSONB arrays
-- Each array contains [{ price, quantity }, ...] sorted appropriately

CREATE TABLE IF NOT EXISTS orderbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    exchange TEXT NOT NULL,
    yes_bids JSONB NOT NULL DEFAULT '[]'::jsonb,
    yes_asks JSONB NOT NULL DEFAULT '[]'::jsonb,
    no_bids JSONB NOT NULL DEFAULT '[]'::jsonb,
    no_asks JSONB NOT NULL DEFAULT '[]'::jsonb,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Ensure one orderbook per market/exchange at a time (or allow multiple for history)
    UNIQUE(market_id, exchange, timestamp)
);

-- Index for fast lookups by market
CREATE INDEX IF NOT EXISTS idx_orderbooks_market_id ON orderbooks(market_id);
CREATE INDEX IF NOT EXISTS idx_orderbooks_exchange ON orderbooks(exchange);
CREATE INDEX IF NOT EXISTS idx_orderbooks_timestamp ON orderbooks(timestamp DESC);

-- Index for latest orderbook per market
CREATE INDEX IF NOT EXISTS idx_orderbooks_market_timestamp ON orderbooks(market_id, timestamp DESC);

