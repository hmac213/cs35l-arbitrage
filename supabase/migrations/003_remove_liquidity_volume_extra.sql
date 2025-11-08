-- Migration: 003_remove_liquidity_volume_extra
-- Description: Remove liquidity, volume, and extra fields from markets table

ALTER TABLE markets
DROP COLUMN IF EXISTS liquidity,
DROP COLUMN IF EXISTS volume,
DROP COLUMN IF EXISTS extra;

