"use client";

import { useState } from "react";
import { MarketPairsWebSocket } from "@/components/MarketPairsWebSocket";

export default function DashboardPage() {
  const [budget, setBudget] = useState<number | null>(null);

  return (
    <MarketPairsWebSocket budget={budget} onBudgetChange={setBudget} />
  );
}
