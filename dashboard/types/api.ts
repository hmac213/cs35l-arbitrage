/**
 * TypeScript type definitions for API responses.
 *
 * These types mirror the backend database models and API response structures.
 * All timestamps are ISO 8601 strings. Nullable fields may be null when data
 * is not yet available (e.g., no orderbook polled yet).
 */

/**
 * Represents a prediction market from either Kalshi or Polymarket exchange.
 * Markets are matched across exchanges to find arbitrage opportunities.
 */
export interface Market {
  /** Database UUID */
  id: string;
  /** Exchange-specific market identifier */
  market_id: string;
  /** Source exchange */
  exchange: "kalshi" | "polymarket";
  /** Human-readable market title/question */
  name: string;
  /** Market resolution rules and criteria */
  rules: string | null;
  /** Date when market resolves (ISO 8601) */
  resolve_date: string | null;
  /** Time when market resolves (ISO 8601) */
  resolve_time: string | null;
  /** Primary category (e.g., "Politics", "Sports") */
  category: string | null;
  /** Secondary category for finer classification */
  subcategory: string | null;
  /** Searchable tags */
  tags: string[] | null;
  /** Detailed market description */
  description: string | null;
  /** Market status: "active", "expired", or "processing" */
  status: string | null;
  /** Last time market data was fetched from exchange */
  last_polled_at: string | null;
  /** Exchange-specific metadata (JSONB) */
  extra: Record<string, any> | null;
  /** Database creation timestamp */
  created_at: string | null;
  /** Database last update timestamp */
  updated_at: string | null;
}

/**
 * Snapshot of a market's orderbook at a point in time.
 * Contains bid/ask arrays for both YES and NO contracts, sorted by price.
 */
export interface Orderbook {
  /** YES contract buy orders, sorted by price descending (best first) */
  yes_bids: Array<{ price: number; quantity: number }>;
  /** YES contract sell orders, sorted by price ascending (best first) */
  yes_asks: Array<{ price: number; quantity: number }>;
  /** NO contract buy orders, sorted by price descending (best first) */
  no_bids: Array<{ price: number; quantity: number }>;
  /** NO contract sell orders, sorted by price ascending (best first) */
  no_asks: Array<{ price: number; quantity: number }>;
  /** When this snapshot was taken */
  timestamp: string | null;
  /** Database creation timestamp */
  created_at: string | null;
}

/**
 * A calculated arbitrage opportunity between two matched markets.
 *
 * Arbitrage exists when: YES_price + NO_price < $1.00 (after fees)
 * Strategy: Buy YES on one exchange and NO on the other. At resolution,
 * exactly one contract pays $1.00, guaranteeing profit.
 */
export interface ArbitrageOpportunity {
  /** Trade direction, e.g., "yes_kalshi_no_polymarket" */
  direction: string;
  /** Exchange where YES contract should be purchased */
  yes_exchange: string;
  /** Exchange where NO contract should be purchased */
  no_exchange: string;
  /** Best available YES price */
  yes_price: number;
  /** Best available NO price */
  no_price: number;
  /** Guaranteed profit per share after fees: $1.00 - (yes + no) × (1 + fees) */
  profit_per_share: number;
  /** Maximum shares executable at these prices (limited by orderbook liquidity) */
  max_size: number;
  /** Trading fee as decimal (e.g., 0.02 = 2%) */
  fees: number;
  /** When this opportunity was calculated */
  timestamp: string | null;
  /** Database creation timestamp */
  created_at: string | null;
}

/**
 * A pair of equivalent markets from different exchanges with arbitrage data.
 *
 * Markets are matched using vector embeddings and LLM verification to ensure
 * they represent the same underlying event/question.
 */
export interface MarketPair {
  /** Database UUID for this pair */
  pair_id: string;
  /** Cosine similarity score from vector embedding comparison (0-1) */
  similarity_score: number;
  /** Whether LLM confirmed markets are semantically identical */
  llm_verified: boolean;
  /** LLM's confidence in the match (0-1), null if not verified */
  llm_confidence: number | null;
  /** When this pair was first created */
  created_at: string | null;
  /** When this pair was last updated */
  updated_at: string | null;
  /** First market in the pair (alphabetically by exchange) */
  market_1: Market;
  /** Second market in the pair */
  market_2: Market;
  /** Latest profitable arbitrage opportunity, null if none exists */
  current_opportunity: ArbitrageOpportunity | null;
  /** Timestamp of most recent opportunity (for sorting) */
  last_opportunity_time: string | null;
  /** Latest orderbook for market_1, null if not yet polled */
  orderbook_1: Orderbook | null;
  /** Latest orderbook for market_2, null if not yet polled */
  orderbook_2: Orderbook | null;
}

