"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface BudgetInputProps {
  budget: number | null;
  onBudgetChange: (budget: number | null) => void;
}

export function BudgetInput({ budget, onBudgetChange }: BudgetInputProps) {
  const [inputValue, setInputValue] = useState<string>(
    budget !== null ? budget.toString() : ""
  );

  useEffect(() => {
    if (budget === null) {
      setInputValue("");
    } else if (budget.toString() !== inputValue) {
      setInputValue(budget.toString());
    }
  }, [budget]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputValue(value);

    // Parse the value, removing any non-numeric characters except decimal point
    const numericValue = parseFloat(value.replace(/[^0-9.]/g, ""));

    if (value === "" || isNaN(numericValue)) {
      onBudgetChange(null);
    } else if (numericValue > 0) {
      onBudgetChange(numericValue);
    }
  };

  const handleClear = () => {
    setInputValue("");
    onBudgetChange(null);
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <label
            htmlFor="budget-input"
            className="mb-1 block text-xs font-medium text-zinc-400"
          >
            Your Budget
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-zinc-500">
              $
            </span>
            <input
              id="budget-input"
              type="text"
              inputMode="decimal"
              value={inputValue}
              onChange={handleInputChange}
              placeholder="Enter your budget"
              className={cn(
                "w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 pl-7 text-sm text-zinc-50 placeholder:text-zinc-600",
                "focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600",
                budget !== null && "border-emerald-500/40 ring-1 ring-emerald-500/20"
              )}
            />
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">
            See how much profit you can make with each opportunity
          </p>
        </div>
        {budget !== null && (
          <button
            onClick={handleClear}
            className="mt-6 flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-50"
            aria-label="Clear budget"
          >
            <X className="h-3 w-3" />
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

