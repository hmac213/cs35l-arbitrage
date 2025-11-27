import { render, screen } from "@testing-library/react";
import { MarketPairCard } from "@/components/MarketPairCard";
import { MarketPair } from "@/types/api";

describe("MarketPairCard Budget Display", () => {
  const mockOpportunity = {
    direction: "yes_kalshi_no_polymarket",
    yes_exchange: "kalshi",
    no_exchange: "polymarket",
    yes_price: 0.45,
    no_price: 0.50,
    profit_per_share: 0.03,
    max_size: 500,
    fees: 0.02,
    timestamp: "2024-01-01T00:00:00Z",
    created_at: "2024-01-01T00:00:00Z",
  };

  const mockMarketPair: MarketPair = {
    pair_id: "test-pair-id",
    similarity_score: 0.95,
    llm_verified: true,
    llm_confidence: 0.9,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    market_1: {
      id: "market-1",
      market_id: "market-1",
      exchange: "kalshi",
      name: "Test Market 1",
      rules: null,
      resolve_date: null,
      resolve_time: null,
      category: null,
      subcategory: null,
      tags: null,
      description: null,
      status: null,
      last_polled_at: null,
      extra: null,
      created_at: null,
      updated_at: null,
    },
    market_2: {
      id: "market-2",
      market_id: "market-2",
      exchange: "polymarket",
      name: "Test Market 2",
      rules: null,
      resolve_date: null,
      resolve_time: null,
      category: null,
      subcategory: null,
      tags: null,
      description: null,
      status: null,
      last_polled_at: null,
      extra: null,
      created_at: null,
      updated_at: null,
    },
    current_opportunity: mockOpportunity,
    last_opportunity_time: "2024-01-01T00:00:00Z",
    orderbook_1: null,
    orderbook_2: null,
  };

  it("should not display budget section when budget is null", () => {
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={null}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.queryByText(/with your budget/i)).not.toBeInTheDocument();
  });

  it("should display budget section when budget is set", () => {
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={100}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.getByText(/with your budget/i)).toBeInTheDocument();
  });

  it("should display budget amount correctly", () => {
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={100}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    // Check that the budget appears in the "With your budget" section
    expect(screen.getByText(/with your budget:/i)).toBeInTheDocument();
    const budgetSection = screen.getByText(/with your budget:/i).parentElement;
    expect(budgetSection).toHaveTextContent(/\$100\.00/);
  });

  it("should display shares you can buy", () => {
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={100}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.getByText(/shares you can buy/i)).toBeInTheDocument();
    // Should show a number for shares
    const sharesText = screen.getByText(/shares you can buy/i).parentElement;
    expect(sharesText).toHaveTextContent(/\d+\.\d+/);
  });

  it("should display total profit", () => {
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={100}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.getByText(/total profit/i)).toBeInTheDocument();
    // Should show currency formatted profit
    const profitText = screen.getByText(/total profit/i).parentElement;
    expect(profitText).toHaveTextContent(/\$\d+\.\d+/);
  });

  it("should display total cost", () => {
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={100}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.getByText(/total cost/i)).toBeInTheDocument();
    // Should show currency formatted cost
    const costText = screen.getByText(/total cost/i).parentElement;
    expect(costText).toHaveTextContent(/\$\d+\.\d+/);
  });

  it("should display ROI percentage", () => {
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={100}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.getByText(/roi/i)).toBeInTheDocument();
    // Should show percentage formatted ROI
    const roiText = screen.getByText(/roi/i).parentElement;
    expect(roiText).toHaveTextContent(/\d+\.\d+%/);
  });

  it("should show max size reached indicator when budget exceeds max_size", () => {
    const largeBudget = 10000; // Large enough to exceed max_size of 500
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={largeBudget}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.getByText(/max size reached/i)).toBeInTheDocument();
  });

  it("should not show max size reached when budget is within max_size", () => {
    render(
      <MarketPairCard
        pair={mockMarketPair}
        onClick={() => {}}
        budget={100}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.queryByText(/max size reached/i)).not.toBeInTheDocument();
  });

  it("should not display budget section when there is no current opportunity", () => {
    const pairWithoutOpportunity: MarketPair = {
      ...mockMarketPair,
      current_opportunity: null,
    };

    render(
      <MarketPairCard
        pair={pairWithoutOpportunity}
        onClick={() => {}}
        budget={100}
        isFavorite={false}
        onToggleFavorite={() => {}}
      />
    );

    expect(screen.queryByText(/with your budget/i)).not.toBeInTheDocument();
  });
});

