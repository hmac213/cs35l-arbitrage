"""Shared dependencies for FastAPI endpoints."""

import os
from db.client import SupabaseClient


def get_db_client() -> SupabaseClient:
    """Get a Supabase database client instance.
    
    Returns:
        SupabaseClient instance configured from environment variables.
    """
    return SupabaseClient()

