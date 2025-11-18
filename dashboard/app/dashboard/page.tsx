"use client";

import { useState, useEffect } from "react";
import { MarketPair } from "@/types/api";
import { MarketPairCards } from "@/components/MarketPairCards";
import { BudgetInput } from "@/components/BudgetInput";

export default function DashboardPage() {
  const [pairs, setPairs] = useState<MarketPair[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [budget, setBudget] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchPairs() {
      try {
        setIsLoading(true);
        // Fetch directly from the FastAPI backend so every reload hits live data.
        const apiBase =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(
          `${apiBase.replace(/\/$/, "")}/api/get_paired_markets`,
          {
            cache: "no-store",
          }
        );

        if (!res.ok) {
          const text = await res.text();
          console.error("Dashboard failed to fetch market pairs:", res.status, text);
          setError(`Failed to load market pairs (${res.status})`);
        } else {
          const data = await res.json();
          setPairs(data);
          setError(null);
        }
      } catch (e) {
        console.error("Dashboard error loading market pairs:", e);
        setError("Unexpected error loading market pairs.");
      } finally {
        setIsLoading(false);
      }
    }
    fetchPairs();
  }, []);

  return (
    <div className="flex w-full flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-zinc-50">
            Market pairs
          </h2>
          <p className="text-xs text-zinc-400">
            Live snapshot fetched from the backend on every page load.
          </p>
        </div>
        <div className="text-right text-xs text-zinc-500">
          {pairs.length > 0 && (
            <span>
              {pairs.length} pair{pairs.length === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>

      <BudgetInput budget={budget} onBudgetChange={setBudget} />

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-950/40 px-3 py-2 text-xs text-red-200">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-6 text-center text-sm text-zinc-400">
          Loading market pairs...
        </div>
      )}

      {!error && !isLoading && pairs.length === 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-6 text-center text-sm text-zinc-400">
          No market pairs found. Once the engine detects arbitrageable pairs,
          they will appear here.
        </div>
      )}

      {!error && !isLoading && pairs.length > 0 && (
        <MarketPairCards pairs={pairs} budget={budget} />
      )}
    </div>
  );
}
