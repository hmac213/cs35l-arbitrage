-- Migration: 009_fix_vector_function_overloading
-- Description: Fix function overloading conflict by dropping old vector-typed functions and ensuring only TEXT versions exist

-- Drop the old functions that accept vector type (if they exist)
DROP FUNCTION IF EXISTS update_market_embedding(UUID, vector);
DROP FUNCTION IF EXISTS search_similar_markets(vector, TEXT, INTEGER, NUMERIC);

-- Ensure the TEXT version of update_market_embedding exists (recreate it to be sure)
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

-- Ensure the TEXT version of search_similar_markets exists (recreate it to be sure)
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

