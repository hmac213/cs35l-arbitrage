"""FastAPI application entry point."""

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints import market_pairs

# Load environment variables from .env file
# Look for .env in the project root (parent of api/ directory)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(
    title="Arbitrage API",
    description="API for accessing arbitrage opportunities between Kalshi and Polymarket",
    version="1.0.0"
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(market_pairs.router, prefix="/api", tags=["market-pairs"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Arbitrage API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

