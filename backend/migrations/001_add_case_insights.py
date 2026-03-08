"""
Migration: Add case_insights table
─────────────────────────────────────────────────────────────────────────────
This migration adds the case_insights table for storing qualitative field
observations and their score adjustments.

Run this migration:
  python -m migrations.001_add_case_insights

Rollback:
  python -m migrations.001_add_case_insights --rollback
─────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import database module
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import engine


MIGRATION_UP = """
CREATE TABLE IF NOT EXISTS case_insights (
    id              TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL,
    notes           TEXT NOT NULL,
    adjustments_json TEXT NOT NULL,
    total_delta     INTEGER NOT NULL,
    created_at      TIMESTAMP NOT NULL,
    created_by      TEXT NOT NULL,
    updated_at      TIMESTAMP NOT NULL,
    
    FOREIGN KEY (case_id) REFERENCES cases(id),
    UNIQUE (case_id)
);

CREATE INDEX IF NOT EXISTS ix_case_insights_case_id ON case_insights(case_id);
CREATE INDEX IF NOT EXISTS ix_case_insights_created_at ON case_insights(created_at);
"""

MIGRATION_DOWN = """
DROP INDEX IF EXISTS ix_case_insights_created_at;
DROP INDEX IF EXISTS ix_case_insights_case_id;
DROP TABLE IF EXISTS case_insights;
"""


async def migrate_up():
    """Apply the migration."""
    print("Applying migration: Add case_insights table...")
    async with engine.begin() as conn:
        # Split by semicolon and execute each statement
        for statement in MIGRATION_UP.strip().split(';'):
            statement = statement.strip()
            if statement:
                await conn.execute(text(statement))
    print("✓ Migration applied successfully")


async def migrate_down():
    """Rollback the migration."""
    print("Rolling back migration: Remove case_insights table...")
    async with engine.begin() as conn:
        # Split by semicolon and execute each statement
        for statement in MIGRATION_DOWN.strip().split(';'):
            statement = statement.strip()
            if statement:
                await conn.execute(text(statement))
    print("✓ Migration rolled back successfully")


async def verify_migration():
    """Verify the migration was applied correctly."""
    print("\nVerifying migration...")
    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='case_insights'"
        ))
        table_exists = result.fetchone() is not None
        
        if table_exists:
            print("✓ Table 'case_insights' exists")
            
            # Check indexes
            result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='case_insights'"
            ))
            indexes = [row[0] for row in result.fetchall()]
            print(f"✓ Indexes created: {', '.join(indexes)}")
            
            # Check columns
            result = await conn.execute(text("PRAGMA table_info(case_insights)"))
            columns = [row[1] for row in result.fetchall()]
            expected_columns = ['id', 'case_id', 'notes', 'adjustments_json', 
                              'total_delta', 'created_at', 'created_by', 'updated_at']
            
            if all(col in columns for col in expected_columns):
                print(f"✓ All expected columns present: {', '.join(expected_columns)}")
            else:
                print(f"⚠ Missing columns. Found: {', '.join(columns)}")
        else:
            print("✗ Table 'case_insights' does not exist")


async def main():
    """Main entry point."""
    if "--rollback" in sys.argv:
        await migrate_down()
    else:
        await migrate_up()
        await verify_migration()


if __name__ == "__main__":
    asyncio.run(main())
