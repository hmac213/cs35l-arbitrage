"use client";

import { useEffect, useCallback } from "react";
import { Sparkles } from "lucide-react";
import { useChat } from "@/contexts/ChatContext";

interface ChatButtonProps {
  className?: string;
}

export function ChatButton({ className }: ChatButtonProps) {
  const { isOpen, setIsOpen } = useChat();

  // Keyboard shortcut: Cmd/Ctrl + K to toggle chat
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      setIsOpen(!isOpen);
    }
  }, [isOpen, setIsOpen]);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <button
      onClick={() => setIsOpen(!isOpen)}
      className={`flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white ${className || ""}`}
      title="Open AI Assistant (⌘K)"
    >
      <Sparkles className="h-4 w-4 text-emerald-400" />
      <span className="hidden sm:inline">AI Assistant</span>
      <kbd className="hidden md:inline-flex items-center gap-1 rounded bg-zinc-700/50 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400">
        <span className="text-[10px]">⌘</span>K
      </kbd>
    </button>
  );
}
