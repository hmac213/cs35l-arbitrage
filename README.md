# Arbitrage Dashboard

A full-stack application for identifying and visualizing arbitrage opportunities between prediction markets on Kalshi and Polymarket. The system uses vector embeddings and LLM verification to match equivalent markets across exchanges, then calculates real-time arbitrage opportunities based on orderbook data.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Database Setup](#database-setup)
- [Backend Setup](#backend-setup)
- [Frontend Setup](#frontend-setup)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

The application consists of three main components:

1. **Backend Services** (Python): Market polling, arbitrage calculation, and WebSocket streaming
2. **API Server** (FastAPI): REST API and WebSocket endpoints for the frontend
3. **Frontend Dashboard** (Next.js): React-based UI for visualizing opportunities

### Data Flow

```
Exchange APIs (Kalshi/Polymarket)
    ↓
Market Poller → Supabase Database
    ↓
Market Similarity Service (Vector Embeddings + LLM Verification)
    ↓
Market Pairs → Orderbook Poller → Arbitrage Calculator
    ↓
WebSocket Stream → Frontend Dashboard
```

## Prerequisites

Before setting up the project, ensure you have:

- **Python 3.10+** (check with `python3 --version`)
- **Node.js 18+** and npm (check with `node --version` and `npm --version`)
- **Supabase Account** (free tier works): [supabase.com](https://supabase.com)
- **OpenAI API Key** (for LLM verification and embeddings): [platform.openai.com](https://platform.openai.com)
- **Kalshi API Credentials** (optional, for authenticated requests)
- **Polymarket API Key** (optional, for authenticated requests)

## Environment Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Arbitrage
```

### 2. Create Environment Files

Create a `.env` file in the project root with the following variables:

```bash
# Supabase Configuration (REQUIRED)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key-here

# OpenAI Configuration (REQUIRED for market matching)
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Optional: Exchange API Keys (for authenticated requests)
KALSHI_API_KEY_ID=your-kalshi-key-id
KALSHI_PRIVATE_KEY=your-kalshi-private-key
POLYMARKET_API_KEY=your-polymarket-api-key

# Optional: Service Configuration
RUN_ARBITRAGE=true
ARBITRAGE_POLL_INTERVAL=60
MARKET_POLL_INTERVAL=3600
USE_WEBSOCKETS=true

# Optional: LLM Verification Settings
LLM_VERIFICATION_ENABLED=true
SIMILARITY_THRESHOLD=0.8

# Optional: CORS Configuration (for API server)
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

### 3. Frontend Environment Variables

Create a `.env.local` file in the `dashboard/` directory:

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Supabase Configuration (for authentication)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
```

**Note:** The Supabase anon key is different from the service role key. Find it in your Supabase project settings under "API" → "Project API keys".

## Database Setup

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Wait for the project to finish provisioning (takes ~2 minutes)
3. Note your project URL and API keys from Settings → API

### 2. Run Database Migrations

The project includes SQL migrations in `supabase/migrations/`. Apply them in order:

**Option A: Using Supabase Dashboard (Recommended)**

1. Open your Supabase project dashboard
2. Go to SQL Editor
3. Run each migration file in order (001 through 019)
4. Or run them all at once by concatenating:

```bash
# From project root
cat supabase/migrations/*.sql | grep -v "^--" | grep -v "^$" > combined_migration.sql
```

Then paste the contents into Supabase SQL Editor and execute.

**Option B: Using Python Script**

```bash
# Activate virtual environment first (see Backend Setup)
python -m db.utils apply_migrations
```

### 3. Verify Database Setup

After migrations, verify these tables exist:
- `markets`
- `market_pairs`
- `orderbooks`
- `arbitrage_opportunities`
- `user_favorites`

## Backend Setup

### 1. Create Python Virtual Environment

```bash
# From project root
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 2. Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Verify Backend Installation

```bash
# Test imports
python -c "from api.main import app; print('Backend imports successful')"
```

## Frontend Setup

### 1. Install Node.js Dependencies

```bash
cd dashboard
npm install
```

### 2. Install Playwright Browsers (for E2E tests)

```bash
npx playwright install
```

### 3. Verify Frontend Installation

```bash
# Check Next.js can start
npm run build
```

## Running the Application

The application requires three services running simultaneously:

### Terminal 1: Backend Services (Market Polling & Arbitrage)

This service polls exchanges, calculates arbitrage opportunities, and streams updates via WebSocket:

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run services
./run_services.sh

# Or manually:
python -m services.main --log-level INFO
```

**What this does:**
- Polls Kalshi and Polymarket for new markets
- Generates embeddings and finds matching markets
- Polls orderbooks and calculates arbitrage opportunities
- Streams updates via WebSocket

### Terminal 2: API Server (FastAPI)

This provides REST endpoints and WebSocket connections for the frontend:

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run API server
./run_api.sh

# Or manually:
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Verify it's running:**
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Terminal 3: Frontend Dashboard (Next.js)

```bash
cd dashboard
npm run dev
```

**Verify it's running:**
- Dashboard: http://localhost:3000
- Login page should be visible

### Accessing the Application

1. **Open browser:** http://localhost:3000
2. **Sign up** for a new account (or sign in if you have one)
3. **Dashboard** will show arbitrage opportunities once backend services populate data

**Note:** It may take a few minutes for the backend to:
- Poll markets from exchanges
- Generate embeddings and find matches
- Calculate initial arbitrage opportunities

## Testing

### Backend Tests (Python)

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_arbitrage_calculator.py
```

### Frontend Tests (Jest)

```bash
cd dashboard

# Run unit/integration tests
npm test

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage
```

### End-to-End Tests (Playwright)

```bash
cd dashboard

# Make sure frontend is running on http://localhost:3000
# Then run E2E tests:
npm run test:e2e

# Or with credentials for login test:
E2E_USER_EMAIL="your-email@example.com" \
E2E_USER_PASSWORD="your-password" \
npm run test:e2e
```

## Project Structure

```
Arbitrage/
├── api/                    # FastAPI application
│   ├── endpoints/          # API route handlers
│   └── main.py            # FastAPI app entry point
├── dashboard/              # Next.js frontend
│   ├── app/               # Next.js App Router pages
│   ├── components/        # React components
│   ├── tests/             # Test files
│   └── package.json       # Node.js dependencies
├── engine/                 # Core business logic
│   ├── arbitrage_calculator.py
│   ├── market_similarity.py
│   └── market_sync.py
├── exchange/               # Exchange API clients
│   └── clients/
│       ├── kalshi_client.py
│       └── polymarket_client.py
├── services/               # Background services
│   └── main.py            # Service orchestration
├── db/                     # Database client and models
├── vector_db/              # Vector embedding operations
├── supabase/
│   └── migrations/        # Database migration files
├── requirements.txt       # Python dependencies
└── .env                   # Environment variables (create this)
```

## Troubleshooting

### Backend Issues

**Problem: `ModuleNotFoundError`**
```bash
# Ensure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

**Problem: `SUPABASE_URL is required`**
- Check that `.env` file exists in project root
- Verify `SUPABASE_URL` and `SUPABASE_KEY` are set correctly
- Ensure `.env` file is not in `.gitignore` (it should be, but make sure it exists locally)

**Problem: `OpenAI API key is required`**
- Add `OPENAI_API_KEY` to `.env` file
- Verify the key is valid at [platform.openai.com](https://platform.openai.com)

**Problem: WebSocket connection fails**
- Ensure API server is running on port 8000
- Check firewall settings
- Verify `USE_WEBSOCKETS=true` in `.env`

### Frontend Issues

**Problem: `Cannot connect to backend`**
- Verify API server is running: http://localhost:8000/health
- Check `NEXT_PUBLIC_API_URL` in `dashboard/.env.local`
- Ensure CORS is configured correctly in `api/main.py`

**Problem: `Supabase auth error`**
- Verify `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `dashboard/.env.local`
- Ensure you're using the **anon key**, not the service role key
- Check Supabase project settings → API → Project API keys

**Problem: Port 3000 already in use**
```bash
# Find and kill process using port 3000
lsof -ti:3000 | xargs kill -9

# Or use a different port
PORT=3001 npm run dev
```

### Database Issues

**Problem: Migration errors**
- Ensure migrations are run in order (001 through 019)
- Check Supabase project has `pgvector` extension enabled
- Verify you're using the service role key (not anon key) for migrations

**Problem: No data appearing**
- Check backend services are running and logging
- Verify markets are being polled: check Supabase `markets` table
- Check `market_pairs` table for matched markets
- Verify `arbitrage_opportunities` table has entries

### Performance Issues

**Problem: Slow market matching**
- Reduce `ASYNC_BATCH_SIZE` in `.env` (default: 20)
- Disable LLM verification temporarily: `LLM_VERIFICATION_ENABLED=false`
- Increase `SIMILARITY_THRESHOLD` to reduce candidates (default: 0.8)

**Problem: High API costs (OpenAI)**
- Disable LLM verification: `LLM_VERIFICATION_ENABLED=false`
- Use cheaper embedding model: `EMBEDDING_MODEL=text-embedding-ada-002`
- Increase polling intervals to reduce API calls

## Additional Resources

- **API Documentation:** See `dashboard/README.md` for frontend API details
- **Supabase Docs:** [supabase.com/docs](https://supabase.com/docs)
- **FastAPI Docs:** [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Next.js Docs:** [nextjs.org/docs](https://nextjs.org/docs)

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review logs from backend services (check terminal output)
3. Verify all environment variables are set correctly
4. Ensure all three services (backend, API, frontend) are running

---

**Last Updated:** 2024

