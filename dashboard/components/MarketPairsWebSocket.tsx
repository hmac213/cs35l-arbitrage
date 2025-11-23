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
}

export function MarketPairsWebSocket({ budget }: MarketPairsWebSocketProps) {
  const [pairs, setPairs] = useState<MarketPair[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch initial data via REST API
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
        
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
    let hasConnectedOnce = false; // Track if we've ever successfully connected
    const maxReconnectAttempts = 5;

    const connect = () => {
      const wsUrl = `${WS_URL}/ws/market_pairs`;
      
      // Only log connection attempts after first successful connection or if it's a retry
      if (hasConnectedOnce || reconnectAttempts > 0) {
        console.log(`Attempting to connect to WebSocket: ${wsUrl} (attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);
      }
      
      // Set a connection timeout
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
      }, 5000); // 5 second timeout
      
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          clearTimeout(connectionTimeout);
          hasConnectedOnce = true; // Mark that we've successfully connected
          reconnectAttempts = 0; // Reset counter on successful connection
          setIsConnected(true);
          setError(null);

          // Send ping every 30 seconds to keep connection alive
          pingInterval = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) {
              ws.send("ping");
            }
          }, 30000);
        };

        ws.onmessage = (event) => {
          try {
            // Handle pong responses (keep-alive)
            if (event.data === "pong") {
              // Silently ignore pong messages - they're just keep-alive responses
              return;
            }

            const data = JSON.parse(event.data);
            
            // Check if it's an error message
            if (data.error) {
              console.error("WebSocket error message:", data.error);
              setError(data.error);
              return;
            }

            // Assume it's an array of market pairs
            if (Array.isArray(data)) {
              setPairs(data);
              setError(null);
            }
          } catch (e) {
            // Only log error if it's not a pong message
            if (event.data !== "pong") {
              console.error("Error parsing WebSocket message:", e, event.data);
              setError("Failed to parse server message");
            }
          }
        };

        ws.onerror = (error) => {
          clearTimeout(connectionTimeout);
          // Only log errors if we've connected before (to avoid React Strict Mode noise)
          if (hasConnectedOnce) {
            console.error("WebSocket error event:", error);
          }
          // Only show error to user if we've connected before
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
          
          // Only log/show errors if we've connected before (to avoid React Strict Mode noise)
          if (hasConnectedOnce) {
            if (event.code === 1006) {
              setError("Cannot connect to WebSocket server. Is the backend running on port 8000?");
            }
          }
          
          // Only reconnect if it wasn't a clean close and we haven't exceeded max attempts
          if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            // Attempt to reconnect after 3 seconds
            reconnectTimeout = setTimeout(() => {
              connect();
            }, 3000);
          } else if (reconnectAttempts >= maxReconnectAttempts && hasConnectedOnce) {
            console.warn("Max WebSocket reconnect attempts reached. Falling back to REST API polling.");
            setError("WebSocket unavailable. Using REST API fallback.");
            // Fallback to REST API polling every 10 seconds
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
        // Only log if we've connected before
        if (hasConnectedOnce) {
          console.error("Error creating WebSocket:", e);
          setError(`Failed to establish WebSocket connection: ${e}. Check if backend is running.`);
        }
        setIsConnected(false);
      }
    };

    // Initial connection
    connect();

    // Cleanup on unmount
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
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-50">
            Market Pairs
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Find arbitrage opportunities across prediction markets
          </p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search markets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 py-2 pl-10 pr-4 text-sm text-zinc-50 placeholder:text-zinc-500 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-950/40 px-3 py-2 text-xs text-red-200">
          {error}
        </div>
      )}

      {!error && pairs.length === 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-6 text-center text-sm text-zinc-400">
          {isConnected
            ? "Waiting for market pairs data..."
            : "Connecting to server..."}
        </div>
      )}

      {!error && pairs.length > 0 && (
        <MarketPairCards pairs={pairs} budget={budget ?? null} searchQuery={searchQuery} />
      )}

      {/* WebSocket Status Indicator */}
      <div className="flex items-center justify-center gap-2 py-4 text-xs text-zinc-500">
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            isConnected ? "bg-emerald-500" : "bg-red-500"
          )}
        />
        <span>
          {isConnected ? "Live updates via WebSocket" : "Disconnected"}
        </span>
        {pairs.length > 0 && (
          <span className="text-zinc-600">
            · {pairs.length} pair{pairs.length === 1 ? "" : "s"} loaded
          </span>
        )}
      </div>
    </div>
  );
}

