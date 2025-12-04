-- Migration: 019_create_get_markets_by_uuids_function
-- Description: Create function to get multiple markets by UUIDs in a single query
--              This is more efficient than making N individual queries

CREATE OR REPLACE FUNCTION get_markets_by_uuids(market_uuids UUID[])
RETURNS TABLE (
    id UUID,
    market_id TEXT,
    exchange TEXT,
    name TEXT,
    rules TEXT,
    resolve_date DATE,
    resolve_time TIME,
    category TEXT,
    subcategory TEXT,
    tags TEXT[],
    description TEXT,
    status TEXT,
    last_polled_at TIMESTAMPTZ,
    extra JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.market_id,
        m.exchange,
        m.name,
        m.rules,
        m.resolve_date,
        m.resolve_time,
        m.category,
        m.subcategory,
        m.tags,
        m.description,
        m.status,
        m.last_polled_at,
        m.extra,
        m.created_at,
        m.updated_at
    FROM markets m
    WHERE m.id = ANY(market_uuids);
END;
$$ LANGUAGE plpgsql;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_markets_by_uuids(UUID[]) TO authenticated;
GRANT EXECUTE ON FUNCTION get_markets_by_uuids(UUID[]) TO anon;

