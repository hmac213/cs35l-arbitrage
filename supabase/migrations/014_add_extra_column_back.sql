-- Migration: 014_add_extra_column_back
-- Description: Add back the extra JSONB column to store exchange-specific data (e.g., token_id for Polymarket)

ALTER TABLE markets
ADD COLUMN IF NOT EXISTS extra JSONB;

-- Create index on extra column for better query performance
CREATE INDEX IF NOT EXISTS idx_markets_extra ON markets USING GIN (extra);

