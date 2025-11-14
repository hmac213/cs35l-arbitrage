# Dashboard Frontend

Next.js dashboard for visualizing arbitrage opportunities.

## Quick Start

1. Install dependencies:
```bash
npm install
```

2. Set environment variables:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. Run development server:
```bash
npm run dev
```

## API Documentation

**For frontend developers:** See the comprehensive API documentation at **[../API_DOCUMENTATION.md](../API_DOCUMENTATION.md)**.

This includes:
- Complete endpoint reference
- Request/response schemas
- Field descriptions and data types
- Example code snippets
- Error handling
- Important notes about null values and data formats

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

## shadcn/ui

This project uses shadcn/ui for UI components. To add a component:

```bash
npx shadcn@latest add button
```

See https://ui.shadcn.com/docs/components for available components.

## TypeScript Types

Type definitions are in `types/api.ts` and match the backend API response structure.
