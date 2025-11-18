import {
  calculateProfitWithBudget,
  formatCurrency,
  formatPercentage,
} from "@/lib/utils";
import { ArbitrageOpportunity } from "@/types/api";

describe("Budget Calculator Utilities", () => {
  describe("calculateProfitWithBudget", () => {
    const sampleOpportunity: ArbitrageOpportunity = {
      direction: "yes_kalshi_no_polymarket",
      yes_exchange: "kalshi",
      no_exchange: "polymarket",
      yes_price: 0.45,
      no_price: 0.50,
      profit_per_share: 0.03,
      max_size: 500,
      fees: 0.02,
      timestamp: "2024-01-01T00:00:00Z",
      created_at: "2024-01-01T00:00:00Z",
    };

    it("should return null for invalid budget (zero)", () => {
      const result = calculateProfitWithBudget(0, sampleOpportunity);
      expect(result).toBeNull();
    });

    it("should return null for invalid budget (negative)", () => {
      const result = calculateProfitWithBudget(-100, sampleOpportunity);
      expect(result).toBeNull();
    });

    it("should return null for null opportunity", () => {
      const result = calculateProfitWithBudget(100, null as any);
      expect(result).toBeNull();
    });

    it("should calculate profit correctly when budget is within max_size", () => {
      const budget = 100;
      const result = calculateProfitWithBudget(budget, sampleOpportunity);

      expect(result).not.toBeNull();
      expect(result!.shares).toBeCloseTo(103.2, 1);
      expect(result!.totalProfit).toBeCloseTo(3.096, 2);
      expect(result!.totalCost).toBeCloseTo(100.0, 1);
      expect(result!.roi).toBeCloseTo(3.096, 2);
      expect(result!.budgetExceeded).toBe(false);
    });

    it("should cap shares at max_size when budget exceeds it", () => {
      const budget = 10000; // Large budget that exceeds max_size
      const result = calculateProfitWithBudget(budget, sampleOpportunity);

      expect(result).not.toBeNull();
      expect(result!.shares).toBe(500); // Capped at max_size
      expect(result!.budgetExceeded).toBe(true);
    });

    it("should calculate correctly with zero fees", () => {
      const opportunityNoFees: ArbitrageOpportunity = {
        ...sampleOpportunity,
        fees: 0,
      };
      const budget = 100;
      const result = calculateProfitWithBudget(budget, opportunityNoFees);

      expect(result).not.toBeNull();
      // Cost per share = 0.45 + 0.50 = 0.95
      // Shares = 100 / 0.95 = 105.26...
      expect(result!.shares).toBeCloseTo(105.26, 1);
      expect(result!.totalProfit).toBeCloseTo(3.158, 2);
    });

    it("should calculate correctly with high fees", () => {
      const opportunityHighFees: ArbitrageOpportunity = {
        ...sampleOpportunity,
        fees: 0.1, // 10% fees
      };
      const budget = 100;
      const result = calculateProfitWithBudget(budget, opportunityHighFees);

      expect(result).not.toBeNull();
      // Cost per share = 0.45 + 0.50 = 0.95
      // Cost with fees = 0.95 * 1.1 = 1.045
      // Shares = 100 / 1.045 = 95.69...
      expect(result!.shares).toBeCloseTo(95.69, 1);
    });

    it("should handle very small budget", () => {
      const budget = 0.5; // Very small budget
      const result = calculateProfitWithBudget(budget, sampleOpportunity);

      expect(result).not.toBeNull();
      expect(result!.shares).toBeGreaterThan(0);
      expect(result!.shares).toBeLessThan(1);
      expect(result!.totalProfit).toBeGreaterThan(0);
    });

    it("should calculate ROI correctly", () => {
      const budget = 100;
      const result = calculateProfitWithBudget(budget, sampleOpportunity);

      expect(result).not.toBeNull();
      // ROI = (totalProfit / totalCost) * 100
      const expectedROI = (result!.totalProfit / result!.totalCost) * 100;
      expect(result!.roi).toBeCloseTo(expectedROI, 2);
    });

    it("should handle opportunity with zero profit per share", () => {
      const zeroProfitOpportunity: ArbitrageOpportunity = {
        ...sampleOpportunity,
        profit_per_share: 0,
      };
      const budget = 100;
      const result = calculateProfitWithBudget(budget, zeroProfitOpportunity);

      expect(result).not.toBeNull();
      expect(result!.totalProfit).toBe(0);
      expect(result!.roi).toBe(0);
    });
  });

  describe("formatCurrency", () => {
    it("should format positive numbers correctly", () => {
      expect(formatCurrency(100)).toBe("$100.00");
      expect(formatCurrency(100.5)).toBe("$100.50");
      expect(formatCurrency(1000.99)).toBe("$1,000.99");
    });

    it("should format negative numbers correctly", () => {
      expect(formatCurrency(-100)).toBe("-$100.00");
      expect(formatCurrency(-100.5)).toBe("-$100.50");
    });

    it("should format zero correctly", () => {
      expect(formatCurrency(0)).toBe("$0.00");
    });

    it("should format very small numbers correctly", () => {
      expect(formatCurrency(0.01)).toBe("$0.01");
      expect(formatCurrency(0.001)).toBe("$0.00");
    });

    it("should format large numbers with commas", () => {
      expect(formatCurrency(1000000)).toBe("$1,000,000.00");
    });
  });

  describe("formatPercentage", () => {
    it("should format positive percentages correctly", () => {
      expect(formatPercentage(5)).toBe("5.00%");
      expect(formatPercentage(5.5)).toBe("5.50%");
      expect(formatPercentage(100)).toBe("100.00%");
    });

    it("should format negative percentages correctly", () => {
      expect(formatPercentage(-5)).toBe("-5.00%");
      expect(formatPercentage(-5.5)).toBe("-5.50%");
    });

    it("should format zero correctly", () => {
      expect(formatPercentage(0)).toBe("0.00%");
    });

    it("should format decimal percentages correctly", () => {
      expect(formatPercentage(3.096)).toBe("3.10%");
      expect(formatPercentage(0.5)).toBe("0.50%");
    });
  });
});

