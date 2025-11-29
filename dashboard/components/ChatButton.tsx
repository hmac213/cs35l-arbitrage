"use client";

import { useState, useEffect } from "react";
import { MessageCircle } from "lucide-react";
import { ChatModal } from "./ChatModal";
import { MarketPair } from "@/types/api";

export function ChatButton() {
  const [isOpen, setIsOpen] = useState(false);
  const [marketPairs, setMarketPairs] = useState<MarketPair[]>([]);

  // Fetch market pairs when chat opens
  useEffect(() => {
    if (isOpen && marketPairs.length === 0) {
      fetch("http://localhost:8000/api/get_paired_markets")
        .then((res) => res.json())
        .then((data) => setMarketPairs(data))
        .catch((err) => console.error("Failed to fetch market pairs:", err));
    }
  }, [isOpen, marketPairs.length]);

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full bg-emerald-600 px-4 py-3 text-white shadow-lg transition hover:bg-emerald-500 hover:shadow-xl"
      >
        <MessageCircle className="h-5 w-5" />
        <span className="text-sm font-medium">Chat</span>
      </button>
      <ChatModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        marketPairs={marketPairs}
      />
    </>
  );
}
