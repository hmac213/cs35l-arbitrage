"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export type SortOption =
  | "recency"
  | "profit_per_share"
  | "total_profit"
  | "profit_with_budget"
  | "max_size"
  | "spread"
  | "none";

export interface SortConfig {
  primary: SortOption;
  secondary: SortOption;
  tertiary: SortOption;
}

export interface FilterOptions {
  minProfit: string;
  maxProfit: string;
  minShares: string;
  maxShares: string;
  minBudgetProfit: string;
  maxBudgetProfit: string;
  showFavoritesOnly: boolean;
}

interface FilterAndSortControlsProps {
  sortConfig: SortConfig;
  onSortChange: (config: SortConfig) => void;
  filters: FilterOptions;
  onFilterChange: (filters: FilterOptions) => void;
  resultCount: number;
  totalCount: number;
  budget: number | null;
  favoritesCount: number;
}

const SORT_OPTIONS: Array<{ value: SortOption; label: string }> = [
  { value: "none", label: "None" },
  { value: "recency", label: "Recency of arbitrage" },
  { value: "profit_per_share", label: "Profit per share" },
  { value: "total_profit", label: "Total profit opportunity" },
  { value: "profit_with_budget", label: "Profit with your budget" },
  { value: "max_size", label: "Total shares to trade" },
  { value: "spread", label: "Spread" },
];

export function FilterAndSortControls({
  sortConfig,
  onSortChange,
  filters,
  onFilterChange,
  resultCount,
  totalCount,
  budget,
  favoritesCount,
}: FilterAndSortControlsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const updateFilter = (key: keyof FilterOptions, value: string) => {
    onFilterChange({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    onFilterChange({
      minProfit: "",
      maxProfit: "",
      minShares: "",
      maxShares: "",
      minBudgetProfit: "",
      maxBudgetProfit: "",
      showFavoritesOnly: false,
    });
  };

  const updateSort = (level: keyof SortConfig, value: SortOption) => {
    onSortChange({ ...sortConfig, [level]: value });
  };

  const getAvailableOptions = (currentLevel: keyof SortConfig) => {
    const used = [
      sortConfig.primary,
      sortConfig.secondary,
      sortConfig.tertiary,
    ].filter((s) => s !== "none");
    const current = sortConfig[currentLevel];

    return SORT_OPTIONS.filter(
      (opt) => {
        // Hide budget-based sort if no budget is set
        if (opt.value === "profit_with_budget" && budget === null) {
          return false;
        }
        return opt.value === "none" || !used.includes(opt.value) || opt.value === current;
      }
    );
  };

  const hasActiveFilters =
    filters.minProfit ||
    filters.maxProfit ||
    filters.minShares ||
    filters.maxShares ||
    filters.minBudgetProfit ||
    filters.maxBudgetProfit ||
    filters.showFavoritesOnly;

  return (
    <div className="space-y-4 rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-zinc-400">Sort:</label>
            <div className="flex items-center gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-zinc-500">Primary</label>
                <select
                  value={sortConfig.primary}
                  onChange={(e) => updateSort("primary", e.target.value as SortOption)}
                  className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-50 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                >
                  {getAvailableOptions("primary").map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-zinc-500">Secondary</label>
                <select
                  value={sortConfig.secondary}
                  onChange={(e) => updateSort("secondary", e.target.value as SortOption)}
                  className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-50 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                >
                  {getAvailableOptions("secondary").map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-zinc-500">Tertiary</label>
                <select
                  value={sortConfig.tertiary}
                  onChange={(e) => updateSort("tertiary", e.target.value as SortOption)}
                  className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-50 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                >
                  {getAvailableOptions("tertiary").map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
          <div className="text-xs text-zinc-500">
            Showing {resultCount} of {totalCount} pair{totalCount === 1 ? "" : "s"}
          </div>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-50"
        >
          Filters
          {hasActiveFilters && (
            <span className="ml-1 rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-[10px] text-emerald-400">
              Active
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-3 w-3 transition-transform",
              isExpanded && "rotate-180"
            )}
          />
        </button>
      </div>

      {isExpanded && (
        <div className="space-y-4 border-t border-zinc-800 pt-4">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-400">
                Min Profit
              </label>
              <input
                type="number"
                step="0.0001"
                value={filters.minProfit}
                onChange={(e) => updateFilter("minProfit", e.target.value)}
                placeholder="0.0000"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-50 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-400">
                Max Profit
              </label>
              <input
                type="number"
                step="0.0001"
                value={filters.maxProfit}
                onChange={(e) => updateFilter("maxProfit", e.target.value)}
                placeholder="No limit"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-50 placeholder:text-zinc-600 focus:border-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-400">
                Min Shares
              </label>
              <input
                type="number"
                step="0.01"
                value={filters.minShares}
                onChange={(e) => updateFilter("minShares", e.target.value)}
                placeholder="0.00"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-50 placeholder:text-zinc-600 focus:border-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-400">
                Max Shares
              </label>
              <input
                type="number"
                step="0.01"
                value={filters.maxShares}
                onChange={(e) => updateFilter("maxShares", e.target.value)}
                placeholder="No limit"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-50 placeholder:text-zinc-600 focus:border-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
          </div>
          {budget !== null && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-emerald-400">
                  Min Profit (Budget)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={filters.minBudgetProfit}
                  onChange={(e) => updateFilter("minBudgetProfit", e.target.value)}
                  placeholder="0.00"
                  className="w-full rounded-md border border-emerald-500/30 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-50 placeholder:text-zinc-600 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-emerald-400">
                  Max Profit (Budget)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={filters.maxBudgetProfit}
                  onChange={(e) => updateFilter("maxBudgetProfit", e.target.value)}
                  placeholder="No limit"
                  className="w-full rounded-md border border-emerald-500/30 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-50 placeholder:text-zinc-600 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
                />
              </div>
            </div>
          )}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-zinc-400 underline transition hover:text-zinc-50"
            >
              Clear all filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}

