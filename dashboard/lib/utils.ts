/**
 * Utility functions for the Arbitrage Dashboard frontend.
 * @module lib/utils
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { ArbitrageOpportunity } from "@/types/api";

/**
 * Merge Tailwind CSS classes with conflict resolution.
 * Combines clsx for conditional classes with tailwind-merge for deduplication.
 *
 * @param inputs - Class values to merge (strings, objects, arrays)
 * @returns Merged class string with conflicts resolved
 * @example cn("px-2 py-1", isActive && "bg-blue-500", "px-4") // "py-1 bg-blue-500 px-4"
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format an ISO 8601 timestamp for display.
 *
 * @param value - ISO timestamp string or null
 * @returns Formatted date string (e.g., "Dec 05, 2025, 07:30 PM") or "N/A" if null
 */
export function formatDateTime(value: string | null): string {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Format a number as USD currency.
 *
 * @param amount - Numeric amount
 * @returns Formatted currency string (e.g., "$1,234.56")
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format a number as a percentage string.
 *
 * @param value - Numeric value (already multiplied by 100)
 * @returns Formatted percentage string (e.g., "12.34%")
 */
export function formatPercentage(value: number): string {
  return `${value.toFixed(2)}%`;
}

export interface BudgetCalculation {
  shares: number;
  totalProfit: number;
  totalCost: number;
  roi: number;
  budgetExceeded: boolean;
}

/**
 * Calculate profit projections for an arbitrage opportunity given a user's budget.
 * 
 * This function implements the core arbitrage profit calculation:
 * - Cost per share = YES price + NO price (both contracts must be purchased)
 * - Fees are applied multiplicatively to the total cost (not additively)
 * - Maximum executable size is constrained by both budget and market liquidity (max_size)
 * - ROI is calculated as (profit / cost) * 100, representing return on investment
 * 
 * Note: The profit_per_share from the opportunity already accounts for the guaranteed
 * $1.00 payout minus costs and fees, so we simply multiply by shares to get total profit.
 * 
 * @param budget - User's available capital in USD
 * @param opportunity - Arbitrage opportunity with prices, fees, and max_size
 * @returns BudgetCalculation with projected shares, profit, cost, ROI, or null if invalid
 */
export function calculateProfitWithBudget(
  budget: number,
  opportunity: ArbitrageOpportunity
): BudgetCalculation | null {
  if (budget <= 0 || !opportunity) {
    return null;
  }

  // Cost per share = YES + NO (both contracts required for arbitrage)
  const costPerShare = opportunity.yes_price + opportunity.no_price;
  // Fees are applied as a multiplier (e.g., 1.02 for 2% fee), not added
  // This matches how exchanges calculate fees on the total trade amount
  const costWithFees = costPerShare * (1 + opportunity.fees);
  // Calculate how many shares the budget can afford
  const maxAffordableShares = budget / costWithFees;
  // Constrain by market liquidity: can't buy more than max_size even if budget allows
  const shares = Math.min(maxAffordableShares, opportunity.max_size);
  // Track if user's budget exceeds available liquidity (useful for UI warnings)
  const budgetExceeded = maxAffordableShares > opportunity.max_size;
  // Total cost = shares * cost per share (with fees already included)
  const totalCost = shares * costWithFees;
  // Total profit = shares * profit per share (profit_per_share already accounts for $1 payout)
  const totalProfit = shares * opportunity.profit_per_share;
  // ROI calculation: avoid division by zero if somehow totalCost is 0
  const roi = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;

  return {
    shares,
    totalProfit,
    totalCost,
    roi,
    budgetExceeded,
  };
}

