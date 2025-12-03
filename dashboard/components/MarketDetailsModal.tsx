"use client";

import { useEffect } from "react";
import { MarketPair } from "@/types/api";
import { OrderbookView } from "./OrderbookView";
import { RelatedNews } from "./RelatedNews";
import { formatDateTime } from "@/lib/utils";
import { X } from "lucide-react";

interface MarketDetailsModalProps {
  pair: MarketPair | null;
  isOpen: boolean;
  onClose: () => void;
}

export function MarketDetailsModal({ pair, isOpen, onClose }: MarketDetailsModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    const handleWheel = (e: WheelEvent) => {
      // Check if the event target is within the modal
      const target = e.target as HTMLElement;
      const modal = document.querySelector('[data-modal="market-details"]');
      
      if (modal && modal.contains(target)) {
        // Allow scrolling within the modal - don't prevent, just stop propagation to background
        e.stopPropagation();
        return;
      }
      
      // Prevent scrolling on the background when modal is open
      if (isOpen) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      document.addEventListener("wheel", handleWheel, { passive: false, capture: true });
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.removeEventListener("wheel", handleWheel, { capture: true });
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  if (!isOpen || !pair) return null;

  const { market_1, market_2, orderbook_1, orderbook_2, current_opportunity } = pair;

  // Determine which side to show for each market based on the opportunity
  const getSideForMarket = (exchange: string): "yes" | "no" => {
    if (!current_opportunity) return "yes"; // Default to YES if no opportunity
    if (exchange === current_opportunity.yes_exchange) return "yes";
    if (exchange === current_opportunity.no_exchange) return "no";
    return "yes"; // Default fallback
  };

  const market1Side = getSideForMarket(market_1.exchange);
  const market2Side = getSideForMarket(market_2.exchange);

  // Remove "Hide From New" from market names
  const cleanMarketName = (name: string) => {
    return name.replace(/Hide From New/gi, "").trim();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
      onWheelCapture={(e) => {
        // Stop propagation in capture phase BEFORE chat sidebar can intercept
        const target = e.target as HTMLElement;
        const modal = e.currentTarget.querySelector('[data-modal="market-details"]');
        if (modal && (modal.contains(target) || target === modal)) {
          e.stopPropagation();
        }
      }}
    >
      <div
        data-modal="market-details"
        data-modal-content
        className="relative w-full max-w-6xl max-h-[90vh] overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        onWheelCapture={(e) => {
          // Stop propagation in capture phase to prevent chat sidebar from intercepting
          e.stopPropagation();
          e.stopImmediatePropagation();
        }}
        style={{ overscrollBehavior: 'contain' }}
      >
        {/* Header */}
        <div className="sticky top-0 z-20 flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-50">Market Details</h2>
            <p className="text-xs text-zinc-400">
              {current_opportunity
                ? `Live arbitrage opportunity detected`
                : `Last opportunity: ${formatDateTime(pair.last_opportunity_time)}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="relative z-0 p-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Market 1 */}
            <div className="space-y-4 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-zinc-50">
                    {cleanMarketName(market_1.name)}
                  </h3>
                  <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-300">
                    {market_1.exchange}
                  </span>
                </div>
                {market_1.status && (
                  <p className="text-xs text-zinc-500">Status: {market_1.status}</p>
                )}
              </div>
              <OrderbookView
                orderbook={orderbook_1}
                marketName={market_1.name}
                exchange={market_1.exchange}
                side={market1Side}
              />
            </div>

            {/* Market 2 */}
            <div className="space-y-4 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-zinc-50">
                    {cleanMarketName(market_2.name)}
                  </h3>
                  <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-300">
                    {market_2.exchange}
                  </span>
                </div>
                {market_2.status && (
                  <p className="text-xs text-zinc-500">Status: {market_2.status}</p>
                )}
              </div>
              <OrderbookView
                orderbook={orderbook_2}
                marketName={market_2.name}
                exchange={market_2.exchange}
                side={market2Side}
              />
            </div>
          </div>

          {/* Arbitrage Opportunity Details */}
          {current_opportunity && (
            <div className="mt-6 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
              <h3 className="mb-3 text-sm font-semibold text-emerald-400">
                Current Arbitrage Opportunity
              </h3>
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <p className="text-xs text-zinc-400">Direction</p>
                  <p className="text-sm font-medium text-zinc-50">
                    Buy YES on {current_opportunity.yes_exchange.charAt(0).toUpperCase() + current_opportunity.yes_exchange.slice(1)}, NO on{" "}
                    {current_opportunity.no_exchange.charAt(0).toUpperCase() + current_opportunity.no_exchange.slice(1)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-zinc-400">Prices</p>
                  <p className="text-sm font-medium text-zinc-50">
                    YES {current_opportunity.yes_price.toFixed(4)} · NO{" "}
                    {current_opportunity.no_price.toFixed(4)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-zinc-400">Profit</p>
                  <p className="text-sm font-medium text-emerald-400">
                    +{current_opportunity.profit_per_share.toFixed(4)} / share
                  </p>
                  <p className="text-xs text-zinc-500">
                    Max size: {current_opportunity.max_size.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Related News Section */}
          <RelatedNews marketName={cleanMarketName(market_1.name)} />
        </div>
      </div>
    </div>
  );
}

