# Dashboard Tests

This directory contains tests for the dashboard application, specifically for the budget calculator feature.

## Setup

Install dependencies (including test dependencies):

```bash
npm install
```

## Running Tests

Run all tests:
```bash
npm test
```

Run tests in watch mode (useful during development):
```bash
npm run test:watch
```

Run tests with coverage report:
```bash
npm run test:coverage
```

## Test Files

- `utils.test.ts` - Tests for budget calculation utilities (`calculateProfitWithBudget`, `formatCurrency`, `formatPercentage`)
- `BudgetInput.test.tsx` - Tests for the BudgetInput component
- `MarketPairCard.budget.test.tsx` - Tests for budget display in MarketPairCard component

## Test Coverage

The tests cover:
- Budget calculation logic with various edge cases
- Currency and percentage formatting
- BudgetInput component interactions
- Budget display in MarketPairCard component
- Handling of invalid inputs and edge cases

