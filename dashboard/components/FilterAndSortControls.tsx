"use client";

import { useState } from "react";
import { ChevronDown, Heart, DollarSign, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type SortOption =
  | "recency"
  | "profit_per_share"
  | "total_profit"
  | "profit_with_budget"
  | "max_size"
  | "spread"
  | "cashout_date"
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
  onBudgetChange?: (budget: number | null) => void;
  favoritesCount: number;
}

const SORT_OPTIONS: Array<{ value: SortOption; label: string }> = [
  { value: "none", label: "None" },
  { value: "recency", label: "Most Recent" },
  { value: "profit_per_share", label: "Profit/Share" },
  { value: "total_profit", label: "Total Profit" },
  { value: "profit_with_budget", label: "Budget Profit" },
  { value: "max_size", label: "Max Shares" },
  { value: "spread", label: "Spread" },
  { value: "cashout_date", label: "Cash Out Date" },
];

export function FilterAndSortControls({
  sortConfig,
  onSortChange,
  filters,
  onFilterChange,
  resultCount,
  totalCount,
  budget,
  onBudgetChange,
  favoritesCount,
}: FilterAndSortControlsProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [budgetInput, setBudgetInput] = useState(budget?.toString() || "");

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

  const handleBudgetChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setBudgetInput(value);
    const numericValue = parseFloat(value.replace(/[^0-9.]/g, ""));
    if (value === "" || isNaN(numericValue)) {
      onBudgetChange?.(null);
    } else if (numericValue > 0) {
      onBudgetChange?.(numericValue);
    }
  };

  const clearBudget = () => {
    setBudgetInput("");
    onBudgetChange?.(null);
  };

  const getAvailableOptions = (currentLevel: keyof SortConfig) => {
    const used = [
      sortConfig.primary,
      sortConfig.secondary,
      sortConfig.tertiary,
    ].filter((s) => s !== "none");
    const current = sortConfig[currentLevel];

    return SORT_OPTIONS.filter((opt) => {
      if (opt.value === "profit_with_budget" && budget === null) {
        return false;
      }
      return opt.value === "none" || !used.includes(opt.value) || opt.value === current;
    });
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
    <div className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
      {/* Main Controls Row */}
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        {/* Left: Sort and Budget */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Sort Selects */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-zinc-500">Sort</span>
            <select
              value={sortConfig.primary}
              onChange={(e) => updateSort("primary", e.target.value as SortOption)}
              className="rounded-md border border-zinc-700 bg-zinc-800 px-2.5 py-1.5 text-xs text-zinc-200 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            >
              {getAvailableOptions("primary").map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              value={sortConfig.secondary}
              onChange={(e) => updateSort("secondary", e.target.value as SortOption)}
              className="rounded-md border border-zinc-700 bg-zinc-800 px-2.5 py-1.5 text-xs text-zinc-200 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            >
              {getAvailableOptions("secondary").map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              value={sortConfig.tertiary}
              onChange={(e) => updateSort("tertiary", e.target.value as SortOption)}
              className="rounded-md border border-zinc-700 bg-zinc-800 px-2.5 py-1.5 text-xs text-zinc-200 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            >
              {getAvailableOptions("tertiary").map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="h-5 w-px bg-zinc-700" />

          {/* Budget Input */}
          {onBudgetChange && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-zinc-500">Budget</span>
              <div className="relative">
                <DollarSign className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
                <input
                  type="text"
                  inputMode="decimal"
                  value={budgetInput}
                  onChange={handleBudgetChange}
                  placeholder="Enter amount"
                  className={cn(
                    "w-32 rounded-md border bg-zinc-800 py-1.5 pl-7 pr-7 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:ring-1",
                    budget !== null
                      ? "border-emerald-500/40 focus:border-emerald-500/50 focus:ring-emerald-500/30"
                      : "border-zinc-700 focus:border-zinc-600 focus:ring-zinc-600"
                  )}
                />
                {budget !== null && (
                  <button
                    onClick={clearBudget}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right: Favorites, Count, Filters */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => onFilterChange({ ...filters, showFavoritesOnly: !filters.showFavoritesOnly })}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition",
              filters.showFavoritesOnly
                ? "border-zinc-600 bg-zinc-700 text-zinc-100"
                : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
            )}
          >
            <Heart
              className={cn(
                "h-3.5 w-3.5",
                filters.showFavoritesOnly ? "fill-current" : ""
              )}
            />
            <span className="hidden sm:inline">Favorites</span>
            {favoritesCount > 0 && (
              <span className="text-zinc-500">({favoritesCount})</span>
            )}
          </button>

          <div className="text-xs text-zinc-500">
            <span className="font-medium text-zinc-300">{resultCount}</span>
            <span> / {totalCount}</span>
          </div>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition",
              isExpanded || hasActiveFilters
                ? "border-zinc-600 bg-zinc-700 text-zinc-100"
                : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
            )}
          >
            Filters
            {hasActiveFilters && (
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-medium text-white">
                {[
                  filters.minProfit,
                  filters.maxProfit,
                  filters.minShares,
                  filters.maxShares,
                  filters.minBudgetProfit,
                  filters.maxBudgetProfit,
                  filters.showFavoritesOnly,
                ].filter(Boolean).length}
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
      </div>

      {/* Expanded Filters */}
      {isExpanded && (
        <div className="space-y-4 border-t border-zinc-800 pt-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label className="mb-1.5 block text-[11px] font-medium text-zinc-400">
                Min Profit/Share
              </label>
              <input
                type="number"
                step="0.0001"
                value={filters.minProfit}
                onChange={(e) => updateFilter("minProfit", e.target.value)}
                placeholder="0.0000"
                className="w-full rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] font-medium text-zinc-400">
                Max Profit/Share
              </label>
              <input
                type="number"
                step="0.0001"
                value={filters.maxProfit}
                onChange={(e) => updateFilter("maxProfit", e.target.value)}
                placeholder="No limit"
                className="w-full rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] font-medium text-zinc-400">
                Min Shares
              </label>
              <input
                type="number"
                step="0.01"
                value={filters.minShares}
                onChange={(e) => updateFilter("minShares", e.target.value)}
                placeholder="0.00"
                className="w-full rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] font-medium text-zinc-400">
                Max Shares
              </label>
              <input
                type="number"
                step="0.01"
                value={filters.maxShares}
                onChange={(e) => updateFilter("maxShares", e.target.value)}
                placeholder="No limit"
                className="w-full rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
          </div>

          {budget !== null && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <label className="mb-1.5 block text-[11px] font-medium text-emerald-400">
                  Min Budget Profit
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={filters.minBudgetProfit}
                  onChange={(e) => updateFilter("minBudgetProfit", e.target.value)}
                  placeholder="$0.00"
                  className="w-full rounded-md border border-emerald-500/30 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[11px] font-medium text-emerald-400">
                  Max Budget Profit
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={filters.maxBudgetProfit}
                  onChange={(e) => updateFilter("maxBudgetProfit", e.target.value)}
                  placeholder="No limit"
                  className="w-full rounded-md border border-emerald-500/30 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
                />
              </div>
            </div>
          )}

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-zinc-400 underline transition hover:text-zinc-200"
            >
              Clear all filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
