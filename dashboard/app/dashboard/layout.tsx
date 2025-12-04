"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import type { User } from "@supabase/supabase-js";
import { cn } from "@/lib/utils";
import { ChatButton } from "@/components/ChatButton";
import { ChatSidebar } from "@/components/ChatSidebar";
import { ChatProvider, useChat } from "@/contexts/ChatContext";
import { MarketPair } from "@/types/api";

function DashboardContent({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { isOpen } = useChat();
  const [marketPairs, setMarketPairs] = useState<MarketPair[]>([]);

  useEffect(() => {
    const getUser = async () => {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      setUser(user);
      setLoading(false);

      if (!user) {
        router.push("/");
      }
    };

    getUser();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      if (!session?.user) {
        router.push("/");
      }
    });

    return () => subscription.unsubscribe();
  }, [router]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.push("/");
  };

  const getUserDisplayName = () => {
    if (!user) return "";
    return user.user_metadata?.full_name || user.email || "";
  };

  // Fetch market pairs when chat opens
  useEffect(() => {
    if (isOpen && marketPairs.length === 0) {
      fetch("http://localhost:8000/api/get_paired_markets")
        .then((res) => res.json())
        .then((data) => setMarketPairs(data))
        .catch((err) => console.error("Failed to fetch market pairs:", err));
    }
  }, [isOpen, marketPairs.length]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <div className="text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ overscrollBehavior: 'none' }}>
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur sticky top-0 z-20">
        <div className={cn(
          "flex flex-1 flex-col px-6 py-4 transition-all duration-300",
          isOpen && "mr-[420px]"
        )}>
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between">
            {/* Left: Logo and Title */}
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold tracking-tight">
                Arbitrage Dashboard
              </h1>
            </div>

            {/* Right: Chat button, User info */}
            <div className="flex items-center gap-4">
              <ChatButton />
              <span className="text-sm text-zinc-400">{getUserDisplayName()}</span>
              <button
                onClick={handleLogout}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white"
              >
                Log out
              </button>
            </div>
          </div>
        </div>
      </header>
      <main className={cn(
        "flex flex-1 flex-col px-6 py-6 transition-all duration-300",
        isOpen && "mr-[420px]"
      )}>
        <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col">
          {children}
        </div>
      </main>
      <ChatSidebar marketPairs={marketPairs} />
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ChatProvider>
      <DashboardContent>{children}</DashboardContent>
    </ChatProvider>
  );
}
