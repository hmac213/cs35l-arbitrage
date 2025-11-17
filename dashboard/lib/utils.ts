import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { ArbitrageOpportunity } from "@/types/api";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

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

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

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

export function calculateProfitWithBudget(
  budget: number,
  opportunity: ArbitrageOpportunity
): BudgetCalculation | null {
  if (budget <= 0 || !opportunity) {
    return null;
  }

  const costPerShare = opportunity.yes_price + opportunity.no_price;
  const costWithFees = costPerShare * (1 + opportunity.fees);
  const maxAffordableShares = budget / costWithFees;
  const shares = Math.min(maxAffordableShares, opportunity.max_size);
  const budgetExceeded = maxAffordableShares > opportunity.max_size;
  const totalCost = shares * costWithFees;
  const totalProfit = shares * opportunity.profit_per_share;
  const roi = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;

  return {
    shares,
    totalProfit,
    totalCost,
    roi,
    budgetExceeded,
  };
}

