-- Migration: 004_remove_image_url
-- Description: Remove image_url field from markets table

ALTER TABLE markets
DROP COLUMN IF EXISTS image_url;

