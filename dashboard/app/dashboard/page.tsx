"use client";

import { useState } from "react";
import { MarketPairsWebSocket } from "@/components/MarketPairsWebSocket";
import { BudgetInput } from "@/components/BudgetInput";

export default function DashboardPage() {
  const [budget, setBudget] = useState<number | null>(null);

  return (
    <div className="flex w-full flex-col gap-4">
      <BudgetInput budget={budget} onBudgetChange={setBudget} />
      <MarketPairsWebSocket budget={budget} />
    </div>
  );
}
