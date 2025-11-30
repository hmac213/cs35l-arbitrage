"use client";

import { useState, useEffect, useCallback } from "react";
import { MessageCircle, X, Sparkles } from "lucide-react";
import { ChatModal } from "./ChatModal";
import { MarketPair } from "@/types/api";

export function ChatButton() {
  const [isOpen, setIsOpen] = useState(false);
  const [marketPairs, setMarketPairs] = useState<MarketPair[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch market pairs when chat opens
  useEffect(() => {
    if (isOpen && marketPairs.length === 0) {
      setIsLoading(true);
      fetch("http://localhost:8000/api/get_paired_markets")
        .then((res) => res.json())
        .then((data) => setMarketPairs(data))
        .catch((err) => console.error("Failed to fetch market pairs:", err))
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, marketPairs.length]);

  // Keyboard shortcut: Cmd/Ctrl + K to toggle chat
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      setIsOpen((prev) => !prev);
    }
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full px-4 py-3 text-white shadow-lg transition-all duration-300 ${
          isOpen
            ? "bg-zinc-700 hover:bg-zinc-600"
            : "bg-emerald-600 hover:bg-emerald-500 hover:shadow-xl hover:scale-105"
        }`}
      >
        {isOpen ? (
          <>
            <X className="h-5 w-5" />
            <span className="text-sm font-medium">Close</span>
          </>
        ) : (
          <>
            <Sparkles className="h-5 w-5" />
            <span className="text-sm font-medium">AI Assistant</span>
            <kbd className="hidden sm:inline-flex items-center gap-1 rounded bg-emerald-700/50 px-1.5 py-0.5 text-[10px] font-medium">
              <span className="text-[10px]">⌘</span>K
            </kbd>
          </>
        )}
      </button>
      <ChatModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        marketPairs={marketPairs}
      />
    </>
  );
}
