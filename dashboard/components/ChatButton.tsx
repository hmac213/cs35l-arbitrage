"use client";

import { useState } from "react";
import { MessageCircle } from "lucide-react";
import { ChatModal } from "./ChatModal";

export function ChatButton() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full bg-emerald-600 px-4 py-3 text-white shadow-lg transition hover:bg-emerald-500 hover:shadow-xl"
      >
        <MessageCircle className="h-5 w-5" />
        <span className="text-sm font-medium">Chat</span>
      </button>
      <ChatModal isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
}
