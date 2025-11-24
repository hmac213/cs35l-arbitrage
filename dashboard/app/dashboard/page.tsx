"use client";

import { useState } from "react";
import { MarketPairsWebSocket } from "@/components/MarketPairsWebSocket";

export default function DashboardPage() {
  const [budget, setBudget] = useState<number | null>(null);

  return (
    <div className="flex w-full flex-col gap-4">
      <MarketPairsWebSocket budget={budget} onBudgetChange={setBudget} />
    </div>
  );
}
