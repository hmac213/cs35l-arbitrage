/** TypeScript type definitions for API responses. */

export interface Market {
  id: string;
  market_id: string;
  exchange: "kalshi" | "polymarket";
  name: string;
  rules: string | null;
  resolve_date: string | null;
  resolve_time: string | null;
  category: string | null;
  subcategory: string | null;
  tags: string[] | null;
  description: string | null;
  status: string | null;
  last_polled_at: string | null;
  extra: Record<string, any> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Orderbook {
  yes_bids: Array<{ price: number; quantity: number }>;
  yes_asks: Array<{ price: number; quantity: number }>;
  no_bids: Array<{ price: number; quantity: number }>;
  no_asks: Array<{ price: number; quantity: number }>;
  timestamp: string | null;
  created_at: string | null;
}

export interface ArbitrageOpportunity {
  direction: string;
  yes_exchange: string;
  no_exchange: string;
  yes_price: number;
  no_price: number;
  profit_per_share: number;
  max_size: number;
  fees: number;
  timestamp: string | null;
  created_at: string | null;
}

export interface MarketPair {
  pair_id: string;
  similarity_score: number;
  llm_verified: boolean;
  llm_confidence: number | null;
  created_at: string | null;
  updated_at: string | null;
  market_1: Market;
  market_2: Market;
  current_opportunity: ArbitrageOpportunity | null;
  last_opportunity_time: string | null;
  orderbook_1: Orderbook | null;
  orderbook_2: Orderbook | null;
}

