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

interface MarketPairCardsProps {
  pairs: MarketPair[];
}

export function MarketPairCards({ pairs }: MarketPairCardsProps) {
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
  });

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
        const result = compareBySortOption(a, b, oppA, oppB, sortBy);
        if (result !== 0) return result;
      }

      return 0;
    });

    return filtered;
  }, [pairs, sortConfig, filters]);

  return (
    <>
      <FilterAndSortControls
        sortConfig={sortConfig}
        onSortChange={setSortConfig}
        filters={filters}
        onFilterChange={setFilters}
        resultCount={filteredAndSortedPairs.length}
        totalCount={pairs.length}
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
  sortBy: SortOption
): number {
  switch (sortBy) {
    case "profit_per_share":
      return oppB.profit_per_share - oppA.profit_per_share;

    case "total_profit": {
      const totalA = oppA.profit_per_share * oppA.max_size;
      const totalB = oppB.profit_per_share * oppB.max_size;
      return totalB - totalA;
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

    case "none":
    default:
      return 0;
  }
}

