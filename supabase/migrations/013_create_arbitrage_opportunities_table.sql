-- Create arbitrage_opportunities table to store calculated arbitrage opportunities
-- Stores historical opportunities with timestamps

CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_pair_id UUID NOT NULL REFERENCES market_pairs(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('yes', 'no')),
    buy_exchange TEXT NOT NULL,
    sell_exchange TEXT NOT NULL,
    buy_price NUMERIC(20, 8) NOT NULL,
    sell_price NUMERIC(20, 8) NOT NULL,
    profit_per_share NUMERIC(20, 8) NOT NULL,
    max_size NUMERIC(20, 8) NOT NULL,
    fees NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_arbitrage_pair_timestamp ON arbitrage_opportunities(market_pair_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_arbitrage_timestamp ON arbitrage_opportunities(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_arbitrage_direction ON arbitrage_opportunities(direction);
CREATE INDEX IF NOT EXISTS idx_arbitrage_profit ON arbitrage_opportunities(profit_per_share DESC);

