"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Send, RefreshCw, X, Loader2, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarketPair } from "@/types/api";
import { useChat } from "@/contexts/ChatContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MarketDetailsModal } from "./MarketDetailsModal";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  marketReferences?: string[]; // Array of pair_ids mentioned in this message
}

interface ChatSidebarProps {
  marketPairs?: MarketPair[];
}

const SAMPLE_MESSAGES = [
  "What's the best opportunity right now?",
  "I have $500, what should I invest in?",
  "Explain how arbitrage works",
  "Which markets have the highest returns?",
];

function formatMarketContext(pairs: MarketPair[]): string {
  if (!pairs || pairs.length === 0) return "";

  const activeOpportunities = pairs.filter((p) => p.current_opportunity);
  const summary = [];

  summary.push(`Total market pairs tracked: ${pairs.length}`);
  summary.push(`Active arbitrage opportunities: ${activeOpportunities.length}`);

  if (activeOpportunities.length > 0) {
    summary.push("\nTop arbitrage opportunities:");
    // Sort by profit and take top 5
    const topOpps = [...activeOpportunities]
      .sort(
        (a, b) =>
          (b.current_opportunity?.profit_per_share || 0) -
          (a.current_opportunity?.profit_per_share || 0)
      )
      .slice(0, 5);

    topOpps.forEach((pair, i) => {
      const opp = pair.current_opportunity!;
      const marketName =
        pair.market_1.exchange === "polymarket"
          ? pair.market_1.name
          : pair.market_2.name;
      summary.push(
        `${i + 1}. "${marketName.substring(0, 50)}${marketName.length > 50 ? "..." : ""}" [pair_id:${pair.pair_id}]`
      );
      summary.push(
        `   - Profit: $${opp.profit_per_share.toFixed(4)}/share (${(opp.profit_per_share * 100).toFixed(2)}%)`
      );
      summary.push(`   - Max size: ${opp.max_size.toFixed(0)} shares`);
      summary.push(
        `   - Potential: $${(opp.profit_per_share * opp.max_size).toFixed(2)} total`
      );
      summary.push(
        `   - Strategy: Buy YES on ${opp.yes_exchange} ($${opp.yes_price.toFixed(2)}), NO on ${opp.no_exchange} ($${opp.no_price.toFixed(2)})`
      );
    });
  }

  return summary.join("\n");
}


const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi! I'm your arbitrage assistant powered by AI. I have access to all current market opportunities and can help you:\n\n• Find the best arbitrage opportunities\n• Calculate potential returns for your budget\n• Explain trading strategies\n• Answer questions about prediction markets\n\nHow can I help you today?",
  timestamp: new Date(),
};

export function ChatSidebar({ marketPairs = [] }: ChatSidebarProps) {
  const { isOpen, setIsOpen } = useChat();
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPair, setSelectedPair] = useState<MarketPair | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Prevent page scroll when mouse is inside chat area
  useEffect(() => {
    if (!isOpen) return;

    let cleanup: (() => void) | null = null;

    // Use a small delay to ensure viewport is rendered
    const timeoutId = setTimeout(() => {
      const scrollArea = scrollAreaRef.current;
      if (!scrollArea) return;

      const sidebar = scrollArea.closest('.fixed');
      if (!sidebar) return;

      const viewport = scrollArea.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement;
      if (!viewport) return;

      const handleWheel = (e: WheelEvent) => {
        // Check if a modal is open - if so, don't interfere with modal scrolling
        const modal = document.querySelector('[data-modal="market-details"]');
        if (modal) {
          const target = e.target as HTMLElement;
          // If the event is within the modal, let it handle its own scrolling
          if (modal.contains(target)) {
            return;
          }
        }

        // Check if the event target is within the chat sidebar
        const target = e.target as HTMLElement;
        if (!sidebar.contains(target)) return;

        // Always prevent page scroll when mouse is in chat area
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        // Manually scroll the viewport
        const { scrollTop, scrollHeight, clientHeight } = viewport;
        const isAtTop = scrollTop <= 1;
        const isAtBottom = scrollTop + clientHeight >= scrollHeight - 1;

        // Only scroll if we're not at boundaries
        if (!(isAtTop && e.deltaY < 0) && !(isAtBottom && e.deltaY > 0)) {
          viewport.scrollTop += e.deltaY;
        }
      };

      // Add listener to document in capture phase to catch all events
      document.addEventListener("wheel", handleWheel, { passive: false, capture: true });

      cleanup = () => {
        document.removeEventListener("wheel", handleWheel, { capture: true });
      };
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      if (cleanup) cleanup();
    };
  }, [isOpen, messages, isModalOpen]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, setIsOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // Prepare messages for API (exclude welcome message, only include conversation)
      const conversationMessages = [...messages, userMessage]
        .filter((m) => m.id !== "welcome")
        .map((m) => ({
          role: m.role,
          content: m.content,
        }));

      // Format market context for AI
      const marketContext = formatMarketContext(marketPairs);

      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: conversationMessages,
          market_context: marketContext || null,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get response");
      }

      const data = await response.json();

      // Validate and extract market references from the API response
      let marketRefs: string[] | undefined = undefined;
      
      if (data.market_references) {
        if (Array.isArray(data.market_references)) {
          // Filter valid pair_ids (UUIDs)
          const validRefs = data.market_references.filter(
            (ref: any) => ref && typeof ref === 'string' && ref.trim().length > 0
          );
          marketRefs = validRefs.length > 0 ? validRefs : undefined;
        } else if (typeof data.market_references === 'string') {
          // Handle case where it might be a string representation
          try {
            const parsed = JSON.parse(data.market_references);
            if (Array.isArray(parsed)) {
              marketRefs = parsed.filter((ref: any) => ref && typeof ref === 'string' && ref.trim().length > 0);
              if (marketRefs.length === 0) marketRefs = undefined;
            }
          } catch (e) {
            // Not valid JSON, ignore
          }
        }
      }

      // Handle case where the response might be a JSON string
      let messageText = data.message;
      let finalMarketRefs = marketRefs;

      // If message is a JSON string, parse it
      if (typeof messageText === 'string' && messageText.trim().startsWith('{') && messageText.trim().endsWith('}')) {
        try {
          const parsed = JSON.parse(messageText);
          if (parsed.message) {
            messageText = parsed.message;
          }
          if (parsed.market_references && !finalMarketRefs) {
            if (Array.isArray(parsed.market_references)) {
              finalMarketRefs = parsed.market_references.filter(
                (ref: any) => ref && typeof ref === 'string' && ref.trim().length > 0
              );
              if (finalMarketRefs.length === 0) finalMarketRefs = undefined;
            }
          }
        } catch (e) {
          // Not JSON, use as-is
          console.warn('Failed to parse message as JSON:', e);
        }
      }

      console.log('Chat response:', { 
        message: messageText, 
        market_references: finalMarketRefs,
        raw_data: data 
      });

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: messageText || "I apologize, but I couldn't generate a response.",
        timestamp: new Date(),
        marketReferences: finalMarketRefs,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content:
          "Sorry, I encountered an error. Please make sure the API server is running and try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 z-10 flex h-screen w-[420px] max-w-[90vw] flex-col border-l border-zinc-800 bg-zinc-950 shadow-2xl">
      {/* Spacer for nav bar */}
      <div className="h-[73px] shrink-0" />
      
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-900/50 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-50">
            Arbitrage Assistant
          </h3>
          <p className="text-xs text-zinc-400">
            {marketPairs.length > 0
              ? `${marketPairs.length} markets loaded`
              : "Powered by AI"}
          </p>
        </div>
        <div className="flex items-center gap-1">
          {messages.length > 1 && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setMessages([WELCOME_MESSAGE])}
              title="Clear chat"
              className="h-8 w-8"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setIsOpen(false)}
            title="Close chat"
            className="h-8 w-8"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div 
        ref={scrollAreaRef}
        className="flex-1 min-h-0"
        style={{ overscrollBehavior: 'contain' }}
      >
        <ScrollArea className="h-full">
          <div className="flex flex-col gap-4 px-4 py-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                "flex transition-opacity duration-300",
                message.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {/* Message bubble */}
              <div className="flex max-w-[85%] flex-col gap-2">
                <div
                  className={cn(
                    "rounded-lg px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap shadow-sm",
                    message.role === "user"
                      ? "bg-emerald-600 text-white"
                      : "bg-zinc-800/80 text-zinc-100"
                  )}
                >
                  {message.content}
                </div>
                
                {/* Market Cards */}
                {message.marketReferences && message.marketReferences.length > 0 && (
                  <div className="flex w-full flex-col gap-2">
                    {message.marketReferences.map((pairId) => {
                      const pair = marketPairs.find((p) => p.pair_id === pairId);
                      if (!pair) {
                        console.warn(`Market pair not found for pair_id: ${pairId}`);
                        return null;
                      }
                      
                      const marketName = pair.market_1.exchange === "polymarket" 
                        ? pair.market_1.name 
                        : pair.market_2.name;
                      const opp = pair.current_opportunity;
                      
                      return (
                        <button
                          key={pairId}
                          onClick={() => {
                            setSelectedPair(pair);
                            setIsModalOpen(true);
                          }}
                          className="group w-full rounded-lg border border-zinc-700 bg-zinc-900/50 p-3 text-left transition hover:border-emerald-500/50 hover:bg-zinc-800/80"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <h4 className="text-xs font-semibold text-zinc-50 break-words group-hover:text-emerald-400 transition-colors">
                                {marketName}
                              </h4>
                              {opp && (
                                <div className="mt-2 space-y-1">
                                  <p className="text-[10px] text-emerald-400">
                                    ${opp.profit_per_share.toFixed(4)}/share profit
                                  </p>
                                  <p className="text-[10px] text-zinc-400">
                                    Max: {opp.max_size.toFixed(0)} shares · ${(opp.profit_per_share * opp.max_size).toFixed(2)} potential
                                  </p>
                                  <p className="text-[10px] text-zinc-500">
                                    Buy YES on {opp.yes_exchange}, NO on {opp.no_exchange}
                                  </p>
                                </div>
                              )}
                            </div>
                            <ExternalLink className="h-3.5 w-3.5 shrink-0 text-zinc-500 group-hover:text-emerald-400 transition-colors mt-0.5" />
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
                
                <span className="px-1 text-[10px] text-zinc-500">
                  {formatTime(message.timestamp)}
                </span>
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="rounded-lg bg-zinc-800/80 px-4 py-3 shadow-sm">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-3 w-3 animate-spin text-emerald-400" />
                  <span className="text-xs text-zinc-400">Analyzing markets...</span>
                </div>
              </div>
            </div>
          )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>
      </div>

      {/* Sample Messages - Integrated into input area */}
      {messages.length === 1 && (
        <div className="shrink-0 border-t border-zinc-800 bg-zinc-900/30 px-4 pt-3 pb-2">
          <div className="flex flex-wrap gap-1.5">
            {SAMPLE_MESSAGES.map((sample, i) => (
              <button
                key={i}
                onClick={() => setInput(sample)}
                className="rounded-md border border-zinc-700/50 bg-zinc-800/30 px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:border-zinc-600 hover:bg-zinc-800/50 hover:text-zinc-300"
              >
                {sample}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="shrink-0 border-t border-zinc-800 bg-zinc-900/50 p-4"
      >
        <div className="flex gap-2">
          <Input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about arbitrage opportunities..."
            className="flex-1 bg-zinc-900/50 border-zinc-700 text-zinc-50 placeholder:text-zinc-500 focus-visible:ring-emerald-500/50"
            disabled={isLoading}
          />
          <Button
            type="submit"
            disabled={!input.trim() || isLoading}
            size="icon"
            className="shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </form>
      
      {/* Market Details Modal - Render via portal to escape stacking context */}
      {typeof window !== 'undefined' && createPortal(
        <MarketDetailsModal
          pair={selectedPair}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedPair(null);
          }}
        />,
        document.body
      )}
    </div>
  );
}
