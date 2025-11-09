-- Migration: 005_create_market_pairs_table
-- Description: Create market_pairs table to store verified matching markets across exchanges

CREATE TABLE IF NOT EXISTS market_pairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_1_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    market_1_exchange TEXT NOT NULL CHECK (market_1_exchange IN ('kalshi', 'polymarket')),
    market_2_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    market_2_exchange TEXT NOT NULL CHECK (market_2_exchange IN ('kalshi', 'polymarket')),
    similarity_score NUMERIC NOT NULL,
    llm_verified BOOLEAN NOT NULL DEFAULT FALSE,
    llm_confidence NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(market_1_id, market_2_id),
    CHECK (market_1_exchange != market_2_exchange)
);

-- Create indexes for commonly queried fields
CREATE INDEX IF NOT EXISTS idx_market_pairs_market_1_id ON market_pairs(market_1_id);
CREATE INDEX IF NOT EXISTS idx_market_pairs_market_2_id ON market_pairs(market_2_id);
CREATE INDEX IF NOT EXISTS idx_market_pairs_market_1_exchange ON market_pairs(market_1_exchange);
CREATE INDEX IF NOT EXISTS idx_market_pairs_market_2_exchange ON market_pairs(market_2_exchange);
CREATE INDEX IF NOT EXISTS idx_market_pairs_llm_verified ON market_pairs(llm_verified);

-- Create function to update updated_at timestamp
CREATE TRIGGER update_market_pairs_updated_at
    BEFORE UPDATE ON market_pairs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

