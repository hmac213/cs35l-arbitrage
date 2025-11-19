"use client";

import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/lib/supabase";

interface UseFavoritesReturn {
  favorites: Set<string>;
  isLoading: boolean;
  toggleFavorite: (pairId: string) => Promise<void>;
  isFavorite: (pairId: string) => boolean;
}

export function useFavorites(): UseFavoritesReturn {
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchFavorites = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        setIsLoading(false);
        return;
      }

      const { data, error } = await supabase
        .from("user_favorites")
        .select("market_pair_id")
        .eq("user_id", user.id);

      if (!error && data) {
        setFavorites(new Set(data.map(f => f.market_pair_id)));
      }
      setIsLoading(false);
    };

    fetchFavorites();
  }, []);

  const toggleFavorite = useCallback(async (pairId: string) => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const isFav = favorites.has(pairId);

    // Optimistic update
    setFavorites(prev => {
      const next = new Set(prev);
      if (isFav) {
        next.delete(pairId);
      } else {
        next.add(pairId);
      }
      return next;
    });

    if (isFav) {
      const { error } = await supabase
        .from("user_favorites")
        .delete()
        .eq("user_id", user.id)
        .eq("market_pair_id", pairId);

      // Revert on error
      if (error) {
        setFavorites(prev => new Set([...prev, pairId]));
      }
    } else {
      const { error } = await supabase
        .from("user_favorites")
        .insert({ user_id: user.id, market_pair_id: pairId });

      // Revert on error
      if (error) {
        setFavorites(prev => {
          const next = new Set(prev);
          next.delete(pairId);
          return next;
        });
      }
    }
  }, [favorites]);

  const isFavorite = useCallback((pairId: string) => {
    return favorites.has(pairId);
  }, [favorites]);

  return { favorites, isLoading, toggleFavorite, isFavorite };
}
