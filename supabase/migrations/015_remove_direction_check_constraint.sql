-- Migration: 015_remove_direction_check_constraint
-- Description: Remove the check constraint on direction column to allow descriptive direction strings
--              like 'yes_kalshi_no_polymarket' instead of just 'yes' or 'no'

ALTER TABLE arbitrage_opportunities
DROP CONSTRAINT IF EXISTS arbitrage_opportunities_direction_check;

