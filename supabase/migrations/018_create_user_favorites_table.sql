-- Migration: 018_create_user_favorites_table
-- Description: Create user_favorites table to store user's favorite market pairs

CREATE TABLE IF NOT EXISTS user_favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    market_pair_id UUID NOT NULL REFERENCES market_pairs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, market_pair_id)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_user_favorites_user_id ON user_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_user_favorites_market_pair_id ON user_favorites(market_pair_id);

-- Enable Row Level Security
ALTER TABLE user_favorites ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own favorites
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname = 'public' 
        AND tablename = 'user_favorites' 
        AND policyname = 'Users can view own favorites'
    ) THEN
        CREATE POLICY "Users can view own favorites"
            ON user_favorites FOR SELECT
            USING (auth.uid() = user_id);
    END IF;
END $$;

-- Policy: Users can only insert their own favorites
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname = 'public' 
        AND tablename = 'user_favorites' 
        AND policyname = 'Users can insert own favorites'
    ) THEN
        CREATE POLICY "Users can insert own favorites"
            ON user_favorites FOR INSERT
            WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

-- Policy: Users can only delete their own favorites
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname = 'public' 
        AND tablename = 'user_favorites' 
        AND policyname = 'Users can delete own favorites'
    ) THEN
        CREATE POLICY "Users can delete own favorites"
            ON user_favorites FOR DELETE
            USING (auth.uid() = user_id);
    END IF;
END $$;
