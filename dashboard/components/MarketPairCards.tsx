"use client";

import { useState, useMemo } from "react";
import { MarketPair } from "@/types/api";
import { MarketPairCard } from "./MarketPairCard";
import { MarketDetailsModal } from "./MarketDetailsModal";
import {
  FilterAndSortControls,
  SortOption,
  SortConfig,
  FilterOptions,
} from "./FilterAndSortControls";
import { calculateProfitWithBudget } from "@/lib/utils";
import { useFavorites } from "@/hooks/useFavorites";

interface MarketPairCardsProps {
  pairs: MarketPair[];
  budget: number | null;
  searchQuery?: string;
}

export function MarketPairCards({ pairs, budget, searchQuery = "" }: MarketPairCardsProps) {
  const [selectedPair, setSelectedPair] = useState<MarketPair | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    primary: "recency",
    secondary: "none",
    tertiary: "none",
  });
  const [filters, setFilters] = useState<FilterOptions>({
    minProfit: "",
    maxProfit: "",
    minShares: "",
    maxShares: "",
    minBudgetProfit: "",
    maxBudgetProfit: "",
    showFavoritesOnly: false,
  });
  const { favorites, toggleFavorite, isFavorite } = useFavorites();

  const handleCardClick = (pair: MarketPair) => {
    setSelectedPair(pair);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedPair(null);
  };

  const filteredAndSortedPairs = useMemo(() => {
    // Apply filters
    let filtered = pairs.filter((pair) => {
      const opp = pair.current_opportunity;
      if (!opp) return false; // Only show pairs with current opportunities

      // Filter by search query
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const market1Name = pair.market_1?.name?.toLowerCase() || "";
        const market2Name = pair.market_2?.name?.toLowerCase() || "";
        if (!market1Name.includes(query) && !market2Name.includes(query)) {
          return false;
        }
      }

      // Filter by favorites
      if (filters.showFavoritesOnly && !favorites.has(pair.pair_id)) {
        return false;
      }

      // Filter by profit
      if (filters.minProfit) {
        const minProfit = parseFloat(filters.minProfit);
        if (isNaN(minProfit) || opp.profit_per_share < minProfit) return false;
      }
      if (filters.maxProfit) {
        const maxProfit = parseFloat(filters.maxProfit);
        if (isNaN(maxProfit) || opp.profit_per_share > maxProfit) return false;
      }

      // Filter by shares (max_size)
      if (filters.minShares) {
        const minShares = parseFloat(filters.minShares);
        if (isNaN(minShares) || opp.max_size < minShares) return false;
      }
      if (filters.maxShares) {
        const maxShares = parseFloat(filters.maxShares);
        if (isNaN(maxShares) || opp.max_size > maxShares) return false;
      }

      // Filter by budget profit
      if (budget !== null && (filters.minBudgetProfit || filters.maxBudgetProfit)) {
        const budgetCalc = calculateProfitWithBudget(budget, opp);
        if (budgetCalc) {
          if (filters.minBudgetProfit) {
            const minBudgetProfit = parseFloat(filters.minBudgetProfit);
            if (isNaN(minBudgetProfit) || budgetCalc.totalProfit < minBudgetProfit) return false;
          }
          if (filters.maxBudgetProfit) {
            const maxBudgetProfit = parseFloat(filters.maxBudgetProfit);
            if (isNaN(maxBudgetProfit) || budgetCalc.totalProfit > maxBudgetProfit) return false;
          }
        }
      }

      return true;
    });

    // Apply multi-level sorting
    filtered.sort((a, b) => {
      const oppA = a.current_opportunity;
      const oppB = b.current_opportunity;

      // If no opportunity, push to bottom
      if (!oppA && !oppB) return 0;
      if (!oppA) return 1;
      if (!oppB) return -1;

      // Apply primary, secondary, and tertiary sorts
      const sortLevels: SortOption[] = [
        sortConfig.primary,
        sortConfig.secondary,
        sortConfig.tertiary,
      ].filter((s) => s !== "none");

      for (const sortBy of sortLevels) {
        const result = compareBySortOption(a, b, oppA, oppB, sortBy, budget);
        if (result !== 0) return result;
      }

      return 0;
    });

    return filtered;
  }, [pairs, sortConfig, filters, budget, favorites, searchQuery]);

  return (
    <>
      <FilterAndSortControls
        sortConfig={sortConfig}
        onSortChange={setSortConfig}
        filters={filters}
        onFilterChange={setFilters}
        resultCount={filteredAndSortedPairs.length}
        totalCount={pairs.length}
        budget={budget}
        favoritesCount={favorites.size}
      />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {filteredAndSortedPairs.length === 0 ? (
          <div className="col-span-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-6 text-center text-sm text-zinc-400">
            No opportunities match your filters. Try adjusting your criteria.
          </div>
        ) : (
          filteredAndSortedPairs.map((pair) => (
            <MarketPairCard
              key={pair.pair_id}
              pair={pair}
              onClick={() => handleCardClick(pair)}
              budget={budget}
              isFavorite={isFavorite(pair.pair_id)}
              onToggleFavorite={() => toggleFavorite(pair.pair_id)}
            />
          ))
        )}
      </div>
      <MarketDetailsModal
        pair={selectedPair}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </>
  );
}

function calculateSpread(pair: MarketPair): number | null {
  const opp = pair.current_opportunity;
  if (!opp) return null;

  // Calculate spread from the opportunity prices
  // Spread is the difference between ask and bid prices
  // For arbitrage, we're buying YES at yes_price and NO at no_price
  // The spread would be related to the bid-ask spread in the orderbook
  // For simplicity, we'll use the price difference as a proxy
  const spread = Math.abs(opp.yes_price + opp.no_price - 1.0);
  return spread;
}

function compareBySortOption(
  a: MarketPair,
  b: MarketPair,
  oppA: NonNullable<MarketPair["current_opportunity"]>,
  oppB: NonNullable<MarketPair["current_opportunity"]>,
  sortBy: SortOption,
  budget: number | null
): number {
  switch (sortBy) {
    case "profit_per_share":
      return oppB.profit_per_share - oppA.profit_per_share;

    case "total_profit": {
      const totalA = oppA.profit_per_share * oppA.max_size;
      const totalB = oppB.profit_per_share * oppB.max_size;
      return totalB - totalA;
    }

    case "profit_with_budget": {
      if (budget === null) return 0;
      const calcA = calculateProfitWithBudget(budget, oppA);
      const calcB = calculateProfitWithBudget(budget, oppB);
      if (!calcA && !calcB) return 0;
      if (!calcA) return 1;
      if (!calcB) return -1;
      return calcB.totalProfit - calcA.totalProfit;
    }

    case "max_size":
      return oppB.max_size - oppA.max_size;

    case "spread": {
      const spreadA = calculateSpread(a);
      const spreadB = calculateSpread(b);
      if (spreadA === null && spreadB === null) return 0;
      if (spreadA === null) return 1;
      if (spreadB === null) return -1;
      return spreadB - spreadA;
    }

    case "recency": {
      const aTime = oppA.timestamp || a.last_opportunity_time;
      const bTime = oppB.timestamp || b.last_opportunity_time;
      if (!aTime && !bTime) return 0;
      if (!aTime) return 1;
      if (!bTime) return -1;
      return new Date(bTime).getTime() - new Date(aTime).getTime();
    }

    case "cashout_date": {
      // Get resolve_date from market_1, fallback to market_2 if null
      const aDate = a.market_1.resolve_date || a.market_2.resolve_date;
      const bDate = b.market_1.resolve_date || b.market_2.resolve_date;
      
      // If both are null, they're equal
      if (!aDate && !bDate) return 0;
      // If a has no date, push it to bottom
      if (!aDate) return 1;
      // If b has no date, push it to bottom
      if (!bDate) return -1;
      
      // Compare dates (earlier dates first - ascending order)
      // This means markets that cash out sooner appear first
      return new Date(aDate).getTime() - new Date(bDate).getTime();
    }

    case "none":
    default:
      return 0;
  }
}

