import { MarketPair } from "@/types/api";
import { cn, formatDateTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

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

function ConfidenceBadge({ pair }: { pair: MarketPair }) {
  if (!pair.llm_verified) {
    return (
      <span className="inline-flex items-center rounded-full bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-400 ring-1 ring-zinc-700">
        Unverified
      </span>
    );
  }

  const confidence = pair.llm_confidence ?? 0;
  const color =
    confidence >= 0.8
      ? "bg-emerald-500/10 text-emerald-400 ring-emerald-500/40"
      : confidence >= 0.5
        ? "bg-amber-500/10 text-amber-400 ring-amber-500/40"
        : "bg-red-500/10 text-red-400 ring-red-500/40";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        color
      )}
    >
      LLM verified · {(confidence * 100).toFixed(0)}%
    </span>
  );
}

function MarketSummary({
  label,
  exchange,
  name,
  status,
  category,
}: {
  label: string;
  exchange: string;
  name: string;
  status: string | null;
  category: string | null;
}) {
  return (
    <div className="space-y-1 rounded-md border border-zinc-800 bg-zinc-900/40 p-3">
      <div className="flex items-center justify-between gap-2 text-xs text-zinc-400">
        <span>{label}</span>
        <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-300">
          {exchange}
        </span>
      </div>
      <p className="line-clamp-2 text-sm font-medium text-zinc-100">{name}</p>
      <div className="flex flex-wrap gap-2 text-xs text-zinc-400">
        {status && (
          <span className="rounded-full bg-zinc-950/40 px-2 py-0.5">
            Status: {status}
          </span>
        )}
        {category && (
          <span className="rounded-full bg-zinc-950/40 px-2 py-0.5">
            {category}
          </span>
        )}
      </div>
    </div>
  );
}

function OpportunityDetails({
  pair,
}: {
  pair: MarketPair;
}) {
  const opp = pair.current_opportunity;

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
        <div className="text-right">
          <p className="text-[11px] uppercase tracking-wide text-zinc-400">
            Similarity
          </p>
          <p className="font-medium text-zinc-50">
            {(pair.similarity_score * 100).toFixed(1)}%
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
              <p className="font-medium text-zinc-50">{opp.direction}</p>
              <p className="text-[11px] text-zinc-400">
                Yes on {opp.yes_exchange}, No on {opp.no_exchange}
              </p>
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
          <div className="flex items-center justify-between text-[11px] text-zinc-400">
            <span>Opportunity created</span>
            <span>{formatDateTime(opp.timestamp ?? opp.created_at)}</span>
          </div>
        </>
      )}
    </div>
  );
}

function MarketPairCard({ pair }: { pair: MarketPair }) {
  const { market_1, market_2 } = pair;

  return (
    <article className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 shadow-sm shadow-zinc-950/40 transition hover:-translate-y-0.5 hover:border-zinc-700 hover:shadow-md hover:shadow-zinc-900/70">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold tracking-tight text-zinc-50">
            {market_1.name} ↔ {market_2.name}
          </h2>
          <p className="text-[11px] text-zinc-400">
            Pair ID: <span className="font-mono text-[10px]">{pair.pair_id}</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <OpportunityBadge pair={pair} />
          <ConfidenceBadge pair={pair} />
        </div>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <MarketSummary
          label="Market 1"
          exchange={market_1.exchange}
          name={market_1.name}
          status={market_1.status}
          category={market_1.category}
        />
        <MarketSummary
          label="Market 2"
          exchange={market_2.exchange}
          name={market_2.name}
          status={market_2.status}
          category={market_2.category}
        />
      </div>

      <OpportunityDetails pair={pair} />
    </article>
  );
}

export default async function Home() {
  let pairs: MarketPair[] = [];
  let error: string | null = null;

  try {
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
      error = `Failed to load market pairs (${res.status})`;
    } else {
      pairs = await res.json();
    }
  } catch (e) {
    console.error("Dashboard error loading market pairs:", e);
    error = "Unexpected error loading market pairs.";
  }

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

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-950/40 px-3 py-2 text-xs text-red-200">
          {error}
        </div>
      )}

      {!error && pairs.length === 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-6 text-center text-sm text-zinc-400">
          No market pairs found. Once the engine detects arbitrageable pairs,
          they will appear here.
        </div>
      )}

      {!error && pairs.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {pairs.map((pair) => (
            <MarketPairCard key={pair.pair_id} pair={pair} />
          ))}
        </div>
      )}
    </div>
  );
}

