"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import type { User } from "@supabase/supabase-js";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

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
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div className="space-y-1">
            <h1 className="text-lg font-semibold tracking-tight">
              Arbitrage Dashboard
            </h1>
            <p className="text-xs text-zinc-400">
              Visualize current and historical opportunities across exchanges.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-300">{getUserDisplayName()}</span>
            <button
              onClick={handleLogout}
              className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-6xl flex-1 px-4 py-6">
        {children}
      </main>
    </div>
  );
}
