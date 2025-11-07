-- Migration: 001_create_markets_table
-- Description: Create unified markets table to store market metadata from both Kalshi and Polymarket

CREATE TABLE IF NOT EXISTS markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id TEXT NOT NULL,
    exchange TEXT NOT NULL CHECK (exchange IN ('kalshi', 'polymarket')),
    name TEXT NOT NULL,
    rules TEXT,
    resolve_date DATE,
    resolve_time TIME,
    category TEXT,
    subcategory TEXT,
    tags TEXT[],
    description TEXT,
    image_url TEXT,
    liquidity NUMERIC,
    volume NUMERIC,
    extra JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(market_id, exchange)
);

-- Create indexes for commonly queried fields
CREATE INDEX IF NOT EXISTS idx_markets_exchange ON markets(exchange);
CREATE INDEX IF NOT EXISTS idx_markets_category ON markets(category);
CREATE INDEX IF NOT EXISTS idx_markets_market_id ON markets(market_id);
CREATE INDEX IF NOT EXISTS idx_markets_resolve_date ON markets(resolve_date);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_markets_updated_at
    BEFORE UPDATE ON markets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

