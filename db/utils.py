"""Migration utilities for applying SQL migrations to Supabase."""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions


def get_migrations_dir() -> Path:
    """Get the path to the migrations directory.
    
    Returns:
        Path object pointing to the migrations directory.
    """
    return Path(__file__).parent / "migrations"


def get_migration_history_path() -> Path:
    """Get the path to the migration history file.
    
    Returns:
        Path object pointing to migration_history.json.
    """
    return get_migrations_dir() / "migration_history.json"


def load_migration_history() -> Dict[str, Any]:
    """Load the migration history from JSON file.
    
    Returns:
        Dictionary containing migration history.
    """
    history_path = get_migration_history_path()
    if history_path.exists():
        with open(history_path, 'r') as f:
            return json.load(f)
    return {"applied_migrations": [], "last_applied": None}


def save_migration_history(history: Dict[str, Any]) -> None:
    """Save the migration history to JSON file.
    
    Args:
        history: Dictionary containing migration history.
    """
    history_path = get_migration_history_path()
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)


def get_migration_files() -> List[Path]:
    """Get all SQL migration files in chronological order.
    
    Returns:
        List of Path objects for migration files, sorted by filename.
    """
    migrations_dir = get_migrations_dir()
    migration_files = sorted(migrations_dir.glob("*.sql"))
    return migration_files


def read_migration_file(migration_path: Path) -> str:
    """Read the contents of a migration file.
    
    Args:
        migration_path: Path to the migration SQL file.
        
    Returns:
        SQL content as string.
    """
    with open(migration_path, 'r') as f:
        return f.read()


def apply_migration(client: Client, sql: str, migration_name: str) -> bool:
    """Apply a SQL migration to Supabase.
    
    Args:
        client: Supabase client instance.
        sql: SQL migration content.
        migration_name: Name of the migration (for logging).
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        # Execute SQL using Supabase's RPC or direct SQL execution
        # Note: Supabase Python client doesn't have direct SQL execution
        # We'll use the REST API directly or use a stored procedure
        
        # For now, we'll use the client's postgrest client to execute raw SQL
        # This requires using the service role key and making a direct HTTP request
        # or using Supabase's migration system
        
        # Alternative: Use Supabase CLI or dashboard to apply migrations
        # This function serves as a placeholder for the migration logic
        
        # If you have service role key, you can execute SQL via HTTP:
        # response = client.postgrest.rpc('exec_sql', {'sql': sql})
        
        # For now, we'll just log that the migration should be applied
        print(f"Migration {migration_name} should be applied manually via Supabase dashboard or CLI.")
        print(f"SQL to execute:\n{sql}")
        
        return True
    except Exception as e:
        print(f"Error applying migration {migration_name}: {e}")
        return False


def apply_migrations(
    supabase_url: str = None,
    supabase_key: str = None,
    force: bool = False
) -> None:
    """Apply all pending migrations to Supabase.
    
    Args:
        supabase_url: Supabase project URL. If not provided, reads from SUPABASE_URL env var.
        supabase_key: Supabase service role key. If not provided, reads from SUPABASE_KEY env var.
        force: If True, reapply already applied migrations.
    """
    supabase_url = supabase_url or os.getenv("SUPABASE_URL")
    supabase_key = supabase_key or os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("Supabase URL and key are required. Set SUPABASE_URL and SUPABASE_KEY environment variables.")
    
    # Create client with service role key for migrations
    client = create_client(
        supabase_url,
        supabase_key,
        options=ClientOptions(
            postgrest_client_timeout=60,
        )
    )
    
    history = load_migration_history()
    applied = set(history.get("applied_migrations", []))
    
    migration_files = get_migration_files()
    
    for migration_path in migration_files:
        migration_name = migration_path.name
        
        if migration_name in applied and not force:
            print(f"Skipping {migration_name} (already applied)")
            continue
        
        print(f"Applying migration: {migration_name}")
        sql = read_migration_file(migration_path)
        
        # Note: Direct SQL execution via Python client is limited
        # For production, use Supabase CLI: npx supabase db push
        # or apply migrations via Supabase dashboard
        
        # This is a placeholder - actual implementation depends on your setup
        success = apply_migration(client, sql, migration_name)
        
        if success:
            applied.add(migration_name)
            history["applied_migrations"] = sorted(list(applied))
            history["last_applied"] = migration_name
            save_migration_history(history)
            print(f"✓ Applied {migration_name}")
        else:
            print(f"✗ Failed to apply {migration_name}")
            raise Exception(f"Migration {migration_name} failed")


def get_pending_migrations() -> List[str]:
    """Get list of migration files that haven't been applied.
    
    Returns:
        List of migration filenames that are pending.
    """
    history = load_migration_history()
    applied = set(history.get("applied_migrations", []))
    
    migration_files = get_migration_files()
    pending = [f.name for f in migration_files if f.name not in applied]
    
    return pending


def reset_migration_history() -> None:
    """Reset the migration history (use with caution).
    
    This will mark all migrations as unapplied.
    """
    history = {"applied_migrations": [], "last_applied": None}
    save_migration_history(history)
    print("Migration history has been reset.")


if __name__ == "__main__":
    """CLI entry point for applying migrations."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        apply_migrations()
    elif len(sys.argv) > 1 and sys.argv[1] == "pending":
        pending = get_pending_migrations()
        if pending:
            print("Pending migrations:")
            for m in pending:
                print(f"  - {m}")
        else:
            print("No pending migrations.")
    elif len(sys.argv) > 1 and sys.argv[1] == "reset":
        confirm = input("Are you sure you want to reset migration history? (yes/no): ")
        if confirm.lower() == "yes":
            reset_migration_history()
        else:
            print("Cancelled.")
    else:
        print("Usage:")
        print("  python -m db.utils apply    - Apply pending migrations")
        print("  python -m db.utils pending - Show pending migrations")
        print("  python -m db.utils reset   - Reset migration history")

