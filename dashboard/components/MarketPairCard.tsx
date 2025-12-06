/**
 * MarketPairCard - Displays a single market pair with arbitrage opportunity details.
 *
 * This component renders a card showing:
 * - Market name (from Polymarket, as it typically has better names)
 * - Live arbitrage badge indicating if opportunity exists
 * - Favorite toggle button
 * - Detailed opportunity information (prices, direction, profit)
 * - Budget-based profit projections if user has set a budget
 */
"use client";

import { Heart } from "lucide-react";
import { MarketPair } from "@/types/api";
import { cn, formatDateTime, calculateProfitWithBudget, formatCurrency, formatPercentage } from "@/lib/utils";

interface MarketPairCardProps {
  /** The market pair data to display */
  pair: MarketPair;
  /** Callback when card is clicked (opens detail modal) */
  onClick: () => void;
  /** User's budget for profit calculations, null if not set */
  budget: number | null;
  /** Whether this pair is in user's favorites */
  isFavorite: boolean;
  /** Callback to toggle favorite status */
  onToggleFavorite: () => void;
}

/**
 * Badge component showing whether a live arbitrage opportunity exists.
 */
function OpportunityBadge({ pair }: { pair: MarketPair }) {
  const hasCurrent = !!pair.current_opportunity;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        hasCurrent
          ? "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/40"
          : "bg-zinc-800 text-zinc-400 ring-1 ring-zinc-700"
      )}
    >
      {hasCurrent ? "Live arbitrage" : "No current arbitrage"}
    </span>
  );
}

/**
 * Convert internal direction string to human-readable format.
 *
 * @param direction - Internal format like "yes_kalshi_no_polymarket"
 * @returns Human-readable string like "Buy YES on Kalshi, NO on Polymarket"
 */
function formatDirection(direction: string): string {
  const parts = direction.split("_");
  if (parts.length >= 4 && parts[0] === "yes" && parts[2] === "no") {
    const yesExchange = parts[1];
    const noExchange = parts[3];

    const capitalizeExchange = (exchange: string): string => {
      return exchange.charAt(0).toUpperCase() + exchange.slice(1);
    };

    return `Buy YES on ${capitalizeExchange(yesExchange)}, NO on ${capitalizeExchange(noExchange)}`;
  }

  return direction;
}

/**
 * Detailed view of the arbitrage opportunity including prices, direction,
 * profit per share, and budget-based calculations if a budget is set.
 */
function OpportunityDetails({
  pair,
  budget,
}: {
  pair: MarketPair;
  budget: number | null;
}) {
  const opp = pair.current_opportunity;
  const budgetCalc = budget !== null && opp ? calculateProfitWithBudget(budget, opp) : null;

  return (
    <div className="mt-4 space-y-3 rounded-md border border-zinc-800 bg-zinc-900/60 p-3 text-xs text-zinc-300">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="space-y-1">
          <p className="text-[11px] uppercase tracking-wide text-zinc-400">
            Last arbitrage
          </p>
          <p className="font-medium text-zinc-50">
            {formatDateTime(pair.last_opportunity_time)}
          </p>
        </div>
      </div>

      {opp && (
        <>
          <div className="h-px bg-gradient-to-r from-zinc-800 via-zinc-700 to-zinc-800" />
          <div className="grid gap-3 md:grid-cols-3">
            <div className="space-y-1">
              <p className="text-[11px] uppercase tracking-wide text-zinc-400">
                Direction
              </p>
              <p className="font-medium text-zinc-50">{formatDirection(opp.direction)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-[11px] uppercase tracking-wide text-zinc-400">
                Prices
              </p>
              <p className="font-medium text-zinc-50">
                Yes {opp.yes_price.toFixed(2)} · No {opp.no_price.toFixed(2)}
              </p>
              <p className="text-[11px] text-zinc-400">
                Fees: {opp.fees.toFixed(4)}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-[11px] uppercase tracking-wide text-zinc-400">
                Edge
              </p>
              <p className="font-medium text-emerald-400">
                +{opp.profit_per_share.toFixed(4)} / share
              </p>
              <p className="text-[11px] text-zinc-400">
                Max size: {opp.max_size.toFixed(2)}
              </p>
            </div>
          </div>
          {budgetCalc && (
            <>
              <div className="h-px bg-gradient-to-r from-zinc-800 via-zinc-700 to-zinc-800" />
              <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-emerald-400">
                    With your budget: {formatCurrency(budget!)}
                  </p>
                  {budgetCalc.budgetExceeded && (
                    <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] text-amber-400">
                      Max size reached
                    </span>
                  )}
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <p className="text-[11px] text-zinc-400">Shares you can buy</p>
                    <p className="font-medium text-zinc-50">
                      {budgetCalc.shares.toFixed(2)}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[11px] text-zinc-400">Total profit</p>
                    <p className="font-medium text-emerald-400">
                      {formatCurrency(budgetCalc.totalProfit)}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[11px] text-zinc-400">Total cost</p>
                    <p className="font-medium text-zinc-50">
                      {formatCurrency(budgetCalc.totalCost)}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[11px] text-zinc-400">ROI</p>
                    <p className="font-medium text-emerald-400">
                      {formatPercentage(budgetCalc.roi)}
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}
          <div className="flex items-center justify-between text-[11px] text-zinc-400">
            <span>Opportunity created</span>
            <span>{formatDateTime(opp.timestamp ?? opp.created_at)}</span>
          </div>
        </>
      )}
    </div>
  );
}

export function MarketPairCard({ pair, onClick, budget, isFavorite, onToggleFavorite }: MarketPairCardProps) {
  const { market_1, market_2 } = pair;

  // Find the Polymarket market to use as the title
  const polymarketMarket = market_1.exchange === "polymarket" ? market_1 : market_2;

  return (
    <article
      onClick={onClick}
      className="flex cursor-pointer flex-col rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 shadow-sm shadow-zinc-950/40 transition hover:-translate-y-0.5 hover:border-zinc-700 hover:shadow-md hover:shadow-zinc-900/70"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-1">
          <h2 className="text-sm font-semibold tracking-tight text-zinc-50">
            {polymarketMarket.name}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite();
            }}
            className="rounded-full p-1.5 transition hover:bg-zinc-800"
            aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
          >
            <Heart
              className={cn(
                "h-4 w-4 transition-colors",
                isFavorite
                  ? "fill-white text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              )}
            />
          </button>
          <OpportunityBadge pair={pair} />
        </div>
      </div>

      <OpportunityDetails pair={pair} budget={budget} />
    </article>
  );
}

