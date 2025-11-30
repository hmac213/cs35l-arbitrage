"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { X, Send, MessageCircle, Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarketPair } from "@/types/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ChatModalProps {
  isOpen: boolean;
  onClose: () => void;
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
        `${i + 1}. "${marketName.substring(0, 50)}${marketName.length > 50 ? "..." : ""}"`
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

export function ChatModal({ isOpen, onClose, marketPairs = [] }: ChatModalProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm your arbitrage assistant. I can help you analyze market opportunities and make informed decisions. How can I help you today?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

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

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.message,
        timestamp: new Date(),
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
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed bottom-20 right-4 z-50 flex w-[420px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 bg-gradient-to-r from-zinc-900 to-zinc-900/50 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-500/10">
              <Bot className="h-5 w-5 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-zinc-50">
                Arbitrage Assistant
              </h3>
              <p className="text-xs text-zinc-400">Powered by AI</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-50"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4" style={{ height: "400px" }}>
          <div className="flex flex-col gap-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex gap-3",
                  message.role === "user" ? "flex-row-reverse" : "flex-row"
                )}
              >
                {/* Avatar */}
                <div
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                    message.role === "user"
                      ? "bg-emerald-500/20"
                      : "bg-zinc-800"
                  )}
                >
                  {message.role === "user" ? (
                    <User className="h-4 w-4 text-emerald-400" />
                  ) : (
                    <Bot className="h-4 w-4 text-zinc-400" />
                  )}
                </div>

                {/* Message bubble */}
                <div
                  className={cn(
                    "flex max-w-[75%] flex-col gap-1",
                    message.role === "user" ? "items-end" : "items-start"
                  )}
                >
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                      message.role === "user"
                        ? "rounded-br-md bg-emerald-600 text-white"
                        : "rounded-bl-md bg-zinc-800 text-zinc-100"
                    )}
                  >
                    {message.content}
                  </div>
                  <span className="px-1 text-[10px] text-zinc-500">
                    {formatTime(message.timestamp)}
                  </span>
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {isLoading && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-800">
                  <Bot className="h-4 w-4 text-zinc-400" />
                </div>
                <div className="rounded-2xl rounded-bl-md bg-zinc-800 px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500" />
                    <span
                      className="h-2 w-2 animate-bounce rounded-full bg-zinc-500"
                      style={{ animationDelay: "0.15s" }}
                    />
                    <span
                      className="h-2 w-2 animate-bounce rounded-full bg-zinc-500"
                      style={{ animationDelay: "0.3s" }}
                    />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Sample Messages */}
        {messages.length === 1 && (
          <div className="border-t border-zinc-800 bg-zinc-900/30 px-4 py-3">
            <p className="mb-2 text-xs text-zinc-500">Try asking:</p>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_MESSAGES.map((sample, i) => (
                <button
                  key={i}
                  onClick={() => setInput(sample)}
                  className="rounded-full border border-zinc-700 bg-zinc-800/50 px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-800"
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
          className="border-t border-zinc-800 bg-zinc-900/50 p-4"
        >
          <div className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about arbitrage opportunities..."
              className="flex-1 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-50 placeholder:text-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
