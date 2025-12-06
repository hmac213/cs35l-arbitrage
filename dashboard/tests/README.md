# Dashboard Tests

This directory contains all tests for the dashboard frontend application.

## Setup

Install dependencies (including test dependencies):

```bash
npm install
```

For E2E tests, also install Playwright browsers:

```bash
npx playwright install
```

## Running Tests

### Unit & Integration Tests (Jest)

```bash
npm test                # Run all tests
npm run test:watch      # Watch mode for development
npm run test:coverage   # Run with coverage report
```

### End-to-End Tests (Playwright)

```bash
# Make sure the frontend is running on localhost:3000
npm run test:e2e
```

## Test Files

### Unit Tests

- `login.test.tsx` - Tests for login page component
- `signup.test.tsx` - Tests for signup page component
- `dashboard-layout.test.tsx` - Tests for dashboard layout component
- `BudgetInput.test.tsx` - Tests for the BudgetInput component
- `MarketPairCard.budget.test.tsx` - Tests for budget display in MarketPairCard
- `utils.test.ts` - Tests for utility functions (budget calculations, formatting)

### E2E Tests (`e2e/`)

- `login.e2e.spec.ts` - End-to-end login flow tests
- `signup.e2e.spec.ts` - End-to-end signup flow tests

## Test Coverage

The tests cover:
- Authentication flows (login, signup)
- Dashboard layout and navigation
- Budget calculation logic with edge cases
- Currency and percentage formatting
- Component interactions and user events
- Form validation and error handling
