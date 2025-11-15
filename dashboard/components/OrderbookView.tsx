"use client";

import { Orderbook } from "@/types/api";
import { cn } from "@/lib/utils";

interface OrderbookViewProps {
  orderbook: Orderbook | null;
  marketName: string;
  exchange: string;
  side: "yes" | "no";
}

export function OrderbookView({ orderbook, marketName, exchange, side }: OrderbookViewProps) {
  if (!orderbook) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950/40 p-8">
        <p className="text-sm text-zinc-500">No orderbook data available</p>
      </div>
    );
  }

  const bids = side === "yes" ? (orderbook.yes_bids || []) : (orderbook.no_bids || []);
  const asks = side === "yes" ? (orderbook.yes_asks || []) : (orderbook.no_asks || []);

  // Reverse asks to show highest first (typical orderbook display)
  const displayAsks = [...asks].slice(0, 10).reverse();
  const displayBids = bids.slice(0, 10);

  // Find the maximum individual quantity among DISPLAYED bids and asks only
  const displayedQuantities = [
    ...displayBids.map((b) => b.quantity),
    ...displayAsks.map((a) => a.quantity),
  ];
  const maxQuantity = displayedQuantities.length > 0 
    ? Math.max(...displayedQuantities) 
    : 1;

  // Normalize so the largest bar is 75% width
  const getBarWidth = (quantity: number) => {
    if (maxQuantity === 0) return 0;
    return (quantity / maxQuantity) * 75;
  };

  const sideLabel = side === "yes" ? "YES" : "NO";
  const isYes = side === "yes";

  return (
    <div className="space-y-3">
        <h4
          className={cn(
            "text-xs font-medium uppercase tracking-wide",
            isYes ? "text-emerald-400" : "text-red-400"
          )}
        >
          {sideLabel}
        </h4>
        <div className="space-y-1">
          {/* Header */}
          <div className="mb-1 grid grid-cols-2 gap-2 text-[10px] text-zinc-500">
            <span className="text-center">Size</span>
            <span className="text-center">Price</span>
          </div>

          {/* Asks (Sell side - top, highest price first) */}
          <div className="space-y-0.5">
            {displayAsks.map((ask, idx) => {
              const widthPercent = getBarWidth(ask.quantity);
              return (
                <div
                  key={idx}
                  className="group relative grid grid-cols-2 gap-2 rounded px-2 py-0.5 text-xs hover:bg-zinc-900/50"
                >
                  <div
                    className={cn(
                      "absolute left-0 top-0 h-full w-full rounded",
                      isYes ? "bg-emerald-500/30" : "bg-red-500/30"
                    )}
                    style={{ width: `${widthPercent}%` }}
                  />
                  <span className="relative z-10 text-center text-zinc-300">
                    {ask.quantity.toFixed(2)}
                  </span>
                  <span
                    className={cn(
                      "relative z-10 text-center font-medium",
                      isYes ? "text-emerald-400" : "text-red-400"
                    )}
                  >
                    {ask.price.toFixed(4)}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Spread indicator */}
          {bids.length > 0 && asks.length > 0 && (
            <div className="my-2 border-t border-zinc-800 py-1 text-center">
              <span className="text-[10px] text-zinc-500">
                Spread:{" "}
                <span className="text-zinc-400 font-medium">
                  {(asks[0].price - bids[0].price).toFixed(4)}
                </span>
              </span>
            </div>
          )}

          {/* Bids (Buy side - bottom, highest price first) */}
          <div className="space-y-0.5">
            {displayBids.map((bid, idx) => {
              const widthPercent = getBarWidth(bid.quantity);
              return (
                <div
                  key={idx}
                  className="group relative grid grid-cols-2 gap-2 rounded px-2 py-0.5 text-xs hover:bg-zinc-900/50"
                >
                  <div
                    className={cn(
                      "absolute left-0 top-0 h-full w-full rounded",
                      isYes ? "bg-red-500/30" : "bg-emerald-500/30"
                    )}
                    style={{ width: `${widthPercent}%` }}
                  />
                  <span className="relative z-10 text-center text-zinc-300">
                    {bid.quantity.toFixed(2)}
                  </span>
                  <span
                    className={cn(
                      "relative z-10 text-center font-medium",
                      isYes ? "text-red-400" : "text-emerald-400"
                    )}
                  >
                    {bid.price.toFixed(4)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
    </div>
  );
}

