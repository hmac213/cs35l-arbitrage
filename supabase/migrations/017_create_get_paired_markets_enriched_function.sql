-- Migration: 017_create_get_paired_markets_enriched_function
-- Description: Create optimized RPC function to fetch all market pairs with enriched data in a single query
--              This replaces N+1 queries with a single efficient SQL query using JOINs and window functions

CREATE OR REPLACE FUNCTION get_paired_markets_enriched()
RETURNS TABLE (
    -- Pair fields
    pair_id UUID,
    similarity_score NUMERIC,
    llm_verified BOOLEAN,
    llm_confidence NUMERIC,
    pair_created_at TIMESTAMPTZ,
    pair_updated_at TIMESTAMPTZ,
    
    -- Market 1 fields
    market_1_id UUID,
    market_1_market_id TEXT,
    market_1_exchange TEXT,
    market_1_name TEXT,
    market_1_rules TEXT,
    market_1_resolve_date DATE,
    market_1_resolve_time TIME,
    market_1_category TEXT,
    market_1_subcategory TEXT,
    market_1_tags TEXT[],
    market_1_description TEXT,
    market_1_status TEXT,
    market_1_last_polled_at TIMESTAMPTZ,
    market_1_extra JSONB,
    market_1_created_at TIMESTAMPTZ,
    market_1_updated_at TIMESTAMPTZ,
    
    -- Market 2 fields
    market_2_id UUID,
    market_2_market_id TEXT,
    market_2_exchange TEXT,
    market_2_name TEXT,
    market_2_rules TEXT,
    market_2_resolve_date DATE,
    market_2_resolve_time TIME,
    market_2_category TEXT,
    market_2_subcategory TEXT,
    market_2_tags TEXT[],
    market_2_description TEXT,
    market_2_status TEXT,
    market_2_last_polled_at TIMESTAMPTZ,
    market_2_extra JSONB,
    market_2_created_at TIMESTAMPTZ,
    market_2_updated_at TIMESTAMPTZ,
    
    -- Orderbook 1 fields
    orderbook_1_id UUID,
    orderbook_1_yes_bids JSONB,
    orderbook_1_yes_asks JSONB,
    orderbook_1_no_bids JSONB,
    orderbook_1_no_asks JSONB,
    orderbook_1_timestamp TIMESTAMPTZ,
    orderbook_1_created_at TIMESTAMPTZ,
    
    -- Orderbook 2 fields
    orderbook_2_id UUID,
    orderbook_2_yes_bids JSONB,
    orderbook_2_yes_asks JSONB,
    orderbook_2_no_bids JSONB,
    orderbook_2_no_asks JSONB,
    orderbook_2_timestamp TIMESTAMPTZ,
    orderbook_2_created_at TIMESTAMPTZ,
    
    -- Arbitrage opportunity fields
    opportunity_id UUID,
    opportunity_direction TEXT,
    opportunity_yes_exchange TEXT,
    opportunity_no_exchange TEXT,
    opportunity_yes_price NUMERIC,
    opportunity_no_price NUMERIC,
    opportunity_profit_per_share NUMERIC,
    opportunity_max_size NUMERIC,
    opportunity_fees NUMERIC,
    opportunity_timestamp TIMESTAMPTZ,
    opportunity_created_at TIMESTAMPTZ
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH latest_orderbooks AS (
        -- Get latest orderbook per market using DISTINCT ON
        SELECT DISTINCT ON (market_id, exchange)
            id,
            market_id,
            exchange,
            yes_bids,
            yes_asks,
            no_bids,
            no_asks,
            timestamp,
            created_at
        FROM orderbooks
        ORDER BY market_id, exchange, timestamp DESC
    ),
    latest_opportunities AS (
        -- Get latest opportunity per market pair using DISTINCT ON
        SELECT DISTINCT ON (market_pair_id)
            id,
            market_pair_id,
            direction,
            yes_exchange,
            no_exchange,
            yes_price,
            no_price,
            profit_per_share,
            max_size,
            fees,
            timestamp,
            created_at
        FROM arbitrage_opportunities
        ORDER BY market_pair_id, timestamp DESC
    )
    SELECT
        -- Pair fields
        mp.id AS pair_id,
        mp.similarity_score,
        mp.llm_verified,
        mp.llm_confidence,
        mp.created_at AS pair_created_at,
        mp.updated_at AS pair_updated_at,
        
        -- Market 1 fields
        m1.id AS market_1_id,
        m1.market_id AS market_1_market_id,
        m1.exchange AS market_1_exchange,
        m1.name AS market_1_name,
        m1.rules AS market_1_rules,
        m1.resolve_date AS market_1_resolve_date,
        m1.resolve_time AS market_1_resolve_time,
        m1.category AS market_1_category,
        m1.subcategory AS market_1_subcategory,
        m1.tags AS market_1_tags,
        m1.description AS market_1_description,
        m1.status AS market_1_status,
        m1.last_polled_at AS market_1_last_polled_at,
        m1.extra AS market_1_extra,
        m1.created_at AS market_1_created_at,
        m1.updated_at AS market_1_updated_at,
        
        -- Market 2 fields
        m2.id AS market_2_id,
        m2.market_id AS market_2_market_id,
        m2.exchange AS market_2_exchange,
        m2.name AS market_2_name,
        m2.rules AS market_2_rules,
        m2.resolve_date AS market_2_resolve_date,
        m2.resolve_time AS market_2_resolve_time,
        m2.category AS market_2_category,
        m2.subcategory AS market_2_subcategory,
        m2.tags AS market_2_tags,
        m2.description AS market_2_description,
        m2.status AS market_2_status,
        m2.last_polled_at AS market_2_last_polled_at,
        m2.extra AS market_2_extra,
        m2.created_at AS market_2_created_at,
        m2.updated_at AS market_2_updated_at,
        
        -- Orderbook 1 fields
        ob1.id AS orderbook_1_id,
        ob1.yes_bids AS orderbook_1_yes_bids,
        ob1.yes_asks AS orderbook_1_yes_asks,
        ob1.no_bids AS orderbook_1_no_bids,
        ob1.no_asks AS orderbook_1_no_asks,
        ob1.timestamp AS orderbook_1_timestamp,
        ob1.created_at AS orderbook_1_created_at,
        
        -- Orderbook 2 fields
        ob2.id AS orderbook_2_id,
        ob2.yes_bids AS orderbook_2_yes_bids,
        ob2.yes_asks AS orderbook_2_yes_asks,
        ob2.no_bids AS orderbook_2_no_bids,
        ob2.no_asks AS orderbook_2_no_asks,
        ob2.timestamp AS orderbook_2_timestamp,
        ob2.created_at AS orderbook_2_created_at,
        
        -- Arbitrage opportunity fields
        opp.id AS opportunity_id,
        opp.direction AS opportunity_direction,
        opp.yes_exchange AS opportunity_yes_exchange,
        opp.no_exchange AS opportunity_no_exchange,
        opp.yes_price AS opportunity_yes_price,
        opp.no_price AS opportunity_no_price,
        opp.profit_per_share AS opportunity_profit_per_share,
        opp.max_size AS opportunity_max_size,
        opp.fees AS opportunity_fees,
        opp.timestamp AS opportunity_timestamp,
        opp.created_at AS opportunity_created_at
        
    FROM market_pairs mp
    INNER JOIN markets m1 ON mp.market_1_id = m1.id
    INNER JOIN markets m2 ON mp.market_2_id = m2.id
    LEFT JOIN latest_orderbooks ob1 ON ob1.market_id = m1.id AND ob1.exchange = m1.exchange
    LEFT JOIN latest_orderbooks ob2 ON ob2.market_id = m2.id AND ob2.exchange = m2.exchange
    LEFT JOIN latest_opportunities opp ON opp.market_pair_id = mp.id
    ORDER BY mp.created_at DESC;
END;
$$;

-- Grant execute permission to authenticated users (adjust as needed for your auth setup)
-- For now, we'll use service role key which has full access
-- GRANT EXECUTE ON FUNCTION get_paired_markets_enriched() TO authenticated;

