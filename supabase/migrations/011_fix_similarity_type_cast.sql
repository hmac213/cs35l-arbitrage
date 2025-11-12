-- Migration: 011_fix_similarity_type_cast
-- Description: Fix similarity column type casting from double precision to NUMERIC

CREATE OR REPLACE FUNCTION search_similar_markets(
    query_embedding TEXT,
    opposing_exchange TEXT,
    result_limit INTEGER DEFAULT 5,
    similarity_threshold NUMERIC DEFAULT 0.8
)
RETURNS TABLE (
    id UUID,
    market_id TEXT,
    exchange TEXT,
    name TEXT,
    rules TEXT,
    resolve_date DATE,
    category TEXT,
    similarity NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    query_vec vector(1536);
BEGIN
    -- Cast text to vector
    query_vec := query_embedding::vector(1536);
    
    RETURN QUERY
    SELECT 
        m.id,
        m.market_id,
        m.exchange,
        m.name,
        m.rules,
        m.resolve_date,
        m.category,
        (1 - (m.embedding <=> query_vec) / 2)::NUMERIC as similarity
    FROM markets m
    WHERE m.exchange = opposing_exchange
      AND m.embedding IS NOT NULL
      AND m.status = 'active'
      AND (1 - (m.embedding <=> query_vec) / 2) >= similarity_threshold
    ORDER BY m.embedding <=> query_vec
    LIMIT result_limit;
END;
$$;

