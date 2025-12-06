# Dashboard Frontend

Next.js 16 dashboard for visualizing arbitrage opportunities between Kalshi and Polymarket prediction markets.

## Quick Start

1. Install dependencies:
```bash
npm install
```

2. Run development server:
```bash
npm run dev
```

3. Open http://localhost:3000 in your browser

**Note:** The dashboard reads environment variables from the root `.env` file (via `next.config.ts`). No separate `.env` file is needed in this directory. The API URL defaults to `http://localhost:8000`. See the main [README.md](../README.md) for complete setup instructions.

## API Documentation

The backend API is documented via FastAPI's built-in OpenAPI/Swagger UI:
- **Swagger UI:** http://localhost:8000/docs (when API server is running)
- **ReDoc:** http://localhost:8000/redoc

Key endpoints:
- `GET /api/get_paired_markets` - Fetch all paired markets with arbitrage opportunities
- `GET /health` - API health check
- `WS /ws/market_pairs` - WebSocket for real-time market updates

## Project Structure

- `app/` - Next.js App Router pages and API routes
- `app/api/` - Next.js API routes that proxy to Python backend
- `types/` - TypeScript type definitions
- `components/` - React components (shadcn/ui)

## API Routes

### `/api/get-paired-markets`

Proxies requests to the Python backend API. The route:
- Fetches data from `NEXT_PUBLIC_API_URL/api/get_paired_markets`
- Caches responses for 30 seconds
- Returns the same data structure as the backend

## Testing

### Unit & Integration Tests (Jest)
```bash
npm test                # Run all tests
npm run test:watch      # Watch mode for development
npm run test:coverage   # Run with coverage report
```

### End-to-End Tests (Playwright)
```bash
# Install Playwright browsers first (one-time setup)
npx playwright install

# Run E2E tests (requires frontend running on localhost:3000)
npm run test:e2e
```

See `tests/README.md` for more details on test coverage.

## shadcn/ui

This project uses shadcn/ui for UI components. To add a component:

```bash
npx shadcn@latest add button
```

See https://ui.shadcn.com/docs/components for available components.

## TypeScript Types

Type definitions are in `types/api.ts` and match the backend API response structure.
