"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { MarketPair } from "@/types/api";
import { MarketPairCards } from "./MarketPairCards";
import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws").replace(/^https/, "wss");

interface MarketPairsWebSocketProps {
  budget?: number | null;
  onBudgetChange?: (budget: number | null) => void;
}

export function MarketPairsWebSocket({ budget, onBudgetChange }: MarketPairsWebSocketProps) {
  const [pairs, setPairs] = useState<MarketPair[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch initial data via REST API
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        const res = await fetch(`${API_URL}/api/get_paired_markets`, {
          cache: "no-store",
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(`HTTP ${res.status}: ${errorText}`);
        }

        const data = await res.json();
        setPairs(data);
        setError(null);
      } catch (e: any) {
        if (e.name === 'AbortError') {
          setError("REST API request timed out. Is the backend running on port 8000?");
        } else if (e.message?.includes('Failed to fetch') || e.message?.includes('NetworkError')) {
          setError("Cannot connect to backend. Is it running on port 8000?");
        } else {
          setError(`Failed to load initial data: ${e.message || e}. Trying WebSocket...`);
        }
      }
    };

    fetchInitialData();
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;
    let pingInterval: NodeJS.Timeout | null = null;
    let fallbackInterval: NodeJS.Timeout | null = null;
    let reconnectAttempts = 0;
    let hasConnectedOnce = false;
    const maxReconnectAttempts = 5;

    const connect = () => {
      const wsUrl = `${WS_URL}/ws/market_pairs`;

      if (hasConnectedOnce || reconnectAttempts > 0) {
        console.log(`Attempting to connect to WebSocket: ${wsUrl} (attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);
      }

      const connectionTimeout = setTimeout(() => {
        if (ws && ws.readyState === WebSocket.CONNECTING) {
          if (hasConnectedOnce) {
            console.error("WebSocket connection timeout");
          }
          ws.close();
          if (!hasConnectedOnce) {
            setError("WebSocket connection timeout - check if backend is running");
          }
          setIsConnected(false);
        }
      }, 5000);

      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          clearTimeout(connectionTimeout);
          hasConnectedOnce = true;
          reconnectAttempts = 0;
          setIsConnected(true);
          setError(null);

          pingInterval = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) {
              ws.send("ping");
            }
          }, 30000);
        };

        ws.onmessage = (event) => {
          try {
            if (event.data === "pong") {
              return;
            }

            const data = JSON.parse(event.data);

            if (data.error) {
              console.error("WebSocket error message:", data.error);
              setError(data.error);
              return;
            }

            if (Array.isArray(data)) {
              setPairs(data);
              setError(null);
            }
          } catch (e) {
            if (event.data !== "pong") {
              console.error("Error parsing WebSocket message:", e, event.data);
              setError("Failed to parse server message");
            }
          }
        };

        ws.onerror = (error) => {
          clearTimeout(connectionTimeout);
          if (hasConnectedOnce) {
            console.error("WebSocket error event:", error);
          }
          if (hasConnectedOnce) {
            setError("WebSocket connection error - check if backend is running on port 8000");
          }
          setIsConnected(false);
        };

        ws.onclose = (event) => {
          clearTimeout(connectionTimeout);
          setIsConnected(false);

          if (pingInterval) {
            clearInterval(pingInterval);
            pingInterval = null;
          }

          if (hasConnectedOnce) {
            if (event.code === 1006) {
              setError("Cannot connect to WebSocket server. Is the backend running on port 8000?");
            }
          }

          if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            reconnectTimeout = setTimeout(() => {
              connect();
            }, 3000);
          } else if (reconnectAttempts >= maxReconnectAttempts && hasConnectedOnce) {
            console.warn("Max WebSocket reconnect attempts reached. Falling back to REST API polling.");
            setError("WebSocket unavailable. Using REST API fallback.");
            fallbackInterval = setInterval(async () => {
              try {
                const res = await fetch(`${API_URL}/api/get_paired_markets`, {
                  cache: "no-store",
                });
                if (res.ok) {
                  const data = await res.json();
                  setPairs(data);
                  setError(null);
                }
              } catch (e) {
                console.error("Fallback REST fetch error:", e);
              }
            }, 10000);
          }
        };
      } catch (e) {
        clearTimeout(connectionTimeout);
        if (hasConnectedOnce) {
          console.error("Error creating WebSocket:", e);
          setError(`Failed to establish WebSocket connection: ${e}. Check if backend is running.`);
        }
        setIsConnected(false);
      }
    };

    connect();

    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (pingInterval) {
        clearInterval(pingInterval);
      }
      if (fallbackInterval) {
        clearInterval(fallbackInterval);
      }
      if (ws) {
        ws.close();
      }
    };
  }, []);

  return (
    <div className="flex w-full flex-col gap-4">
      {/* Status and Search Row */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              isConnected ? "bg-emerald-500" : "bg-zinc-600"
            )}
          />
          <span>{isConnected ? "Live" : "Offline"}</span>
          {pairs.length > 0 && (
            <>
              <span className="text-zinc-700">·</span>
              <span>{pairs.length} pairs</span>
            </>
          )}
        </div>

        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search markets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/50 py-2 pl-10 pr-4 text-sm text-zinc-50 placeholder:text-zinc-500 transition focus:border-zinc-700 focus:bg-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-700"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-4">
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}

        {!error && pairs.length === 0 && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 px-4 py-12 text-center">
            <p className="text-sm text-zinc-400">
              {isConnected
                ? "Waiting for market pairs data..."
                : "Connecting to server..."}
            </p>
          </div>
        )}

        {!error && pairs.length > 0 && (
          <MarketPairCards
            pairs={pairs}
            budget={budget ?? null}
            onBudgetChange={onBudgetChange}
            searchQuery={searchQuery}
          />
        )}
      </div>
    </div>
  );
}
