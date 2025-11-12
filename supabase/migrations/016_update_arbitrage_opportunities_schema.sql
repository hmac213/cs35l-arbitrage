-- Migration: 016_update_arbitrage_opportunities_schema
-- Description: Update arbitrage_opportunities table to reflect new arbitrage strategy
--              Change from buy_exchange/sell_exchange/buy_price/sell_price
--              to yes_exchange/no_exchange/yes_price/no_price (all buys)

-- Delete all existing records to start fresh
DELETE FROM arbitrage_opportunities;

-- Drop old columns
ALTER TABLE arbitrage_opportunities
DROP COLUMN IF EXISTS buy_exchange,
DROP COLUMN IF EXISTS sell_exchange,
DROP COLUMN IF EXISTS buy_price,
DROP COLUMN IF EXISTS sell_price;

-- Add new columns
ALTER TABLE arbitrage_opportunities
ADD COLUMN yes_exchange TEXT NOT NULL,
ADD COLUMN no_exchange TEXT NOT NULL,
ADD COLUMN yes_price NUMERIC(20, 8) NOT NULL,
ADD COLUMN no_price NUMERIC(20, 8) NOT NULL;

-- Update indexes (drop old ones if they reference dropped columns, add new ones)
DROP INDEX IF EXISTS idx_arbitrage_direction;
CREATE INDEX IF NOT EXISTS idx_arbitrage_direction ON arbitrage_opportunities(direction);
CREATE INDEX IF NOT EXISTS idx_arbitrage_exchanges ON arbitrage_opportunities(yes_exchange, no_exchange);

