-- Migration: 002_add_market_status
-- Description: Add status tracking and timestamps to markets table for data engine

-- Add status field with constraint
ALTER TABLE markets 
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active' 
CHECK (status IN ('active', 'expired', 'processing'));

-- Add last_polled_at timestamp to track when market was last fetched
ALTER TABLE markets 
ADD COLUMN IF NOT EXISTS last_polled_at TIMESTAMP WITH TIME ZONE;

-- Add index on status for efficient queries
CREATE INDEX IF NOT EXISTS idx_markets_status ON markets(status);

-- Add index on resolve_date and resolve_time for expiration queries
-- (resolve_date already has an index, but we'll add a composite one for expiration checks)
CREATE INDEX IF NOT EXISTS idx_markets_resolve_datetime ON markets(resolve_date, resolve_time) 
WHERE resolve_date IS NOT NULL AND resolve_time IS NOT NULL;

-- Add index on last_polled_at for tracking stale data
CREATE INDEX IF NOT EXISTS idx_markets_last_polled_at ON markets(last_polled_at);

-- Update existing markets to have 'active' status if null
UPDATE markets SET status = 'active' WHERE status IS NULL;

-- Set last_polled_at to created_at for existing markets
UPDATE markets SET last_polled_at = created_at WHERE last_polled_at IS NULL;

