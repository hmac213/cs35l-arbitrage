-- Migration: 008_update_vector_functions_for_rpc
-- Description: Update vector functions to accept TEXT parameters for RPC calls

-- Function to update market embedding
-- Accepts embedding as TEXT and casts to vector type (for RPC compatibility)
CREATE OR REPLACE FUNCTION update_market_embedding(
    market_uuid UUID,
    embedding_vector TEXT
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE markets
    SET embedding = embedding_vector::vector(1536)
    WHERE id = market_uuid;
END;
$$;

-- Function to search for similar markets
-- Accepts embedding as TEXT and casts to vector type (for RPC compatibility)
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
        1 - (m.embedding <=> query_vec) / 2 as similarity
    FROM markets m
    WHERE m.exchange = opposing_exchange
      AND m.embedding IS NOT NULL
      AND m.status = 'active'
      AND (1 - (m.embedding <=> query_vec) / 2) >= similarity_threshold
    ORDER BY m.embedding <=> query_vec
    LIMIT result_limit;
END;
$$;

