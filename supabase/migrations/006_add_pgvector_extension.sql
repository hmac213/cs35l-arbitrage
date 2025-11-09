-- Migration: 006_add_pgvector_extension
-- Description: Enable pgvector extension and add embedding column to markets table

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to markets table
ALTER TABLE markets
ADD COLUMN IF NOT EXISTS embedding vector(1536); -- text-embedding-3-small produces 1536 dimensions (fits within pgvector index limits)

-- Create index for vector similarity search (using cosine distance)
-- Using IVFFlat for efficient approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS idx_markets_embedding_cosine 
ON markets 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index for exchange filtering (for efficient filtered searches)
CREATE INDEX IF NOT EXISTS idx_markets_exchange_embedding 
ON markets(exchange) 
WHERE embedding IS NOT NULL;

