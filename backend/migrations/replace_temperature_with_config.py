#!/usr/bin/env python3
"""
Migration script to replace llm_temperature column with temperature_config in sessions table.

Migrates existing single temperature values to per-step JSON configuration.

Run this script to migrate an existing database:
    python migrations/replace_temperature_with_config.py

This is safe to run multiple times - it checks if columns exist first.
"""

import sqlite3
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def migrate():
    """Replace llm_temperature with temperature_config column."""
    db_path = settings.database_url.replace("sqlite:///", "")

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("The column will be created automatically when you start the app.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]

        # Already migrated
        if "temperature_config" in columns and "llm_temperature" not in columns:
            print("Migration already applied: 'temperature_config' exists and 'llm_temperature' is gone.")
            return

        # Step 1: Add temperature_config if it doesn't exist yet
        if "temperature_config" not in columns:
            print("Adding 'temperature_config' column...")
            cursor.execute("ALTER TABLE sessions ADD COLUMN temperature_config TEXT")

        # Step 2: Migrate existing llm_temperature values to temperature_config JSON
        if "llm_temperature" in columns:
            print("Migrating existing temperature values...")
            cursor.execute("SELECT id, llm_temperature FROM sessions WHERE llm_temperature IS NOT NULL")
            rows = cursor.fetchall()
            for row_id, temp_val in rows:
                config = {
                    "brainstorming": temp_val,
                    "consultation": temp_val,
                    "business_case": temp_val,
                    "cost_estimation": temp_val,
                    "extraction": temp_val,
                    "export": temp_val,
                }
                cursor.execute(
                    "UPDATE sessions SET temperature_config = ? WHERE id = ?",
                    (json.dumps(config), row_id)
                )
            print(f"Migrated {len(rows)} session(s) with temperature values.")

            # Step 3: Drop llm_temperature column (SQLite requires table recreation)
            print("Dropping 'llm_temperature' column (recreating table)...")

            # Get current column info to rebuild table
            cursor.execute("PRAGMA table_info(sessions)")
            all_columns = cursor.fetchall()
            # all_columns: (cid, name, type, notnull, dflt_value, pk)

            # Build column list excluding llm_temperature
            keep_columns = [col for col in all_columns if col[1] != "llm_temperature"]
            col_names = [col[1] for col in keep_columns]
            col_names_str = ", ".join(col_names)

            # Build CREATE TABLE statement for new table
            col_defs = []
            for col in keep_columns:
                cid, name, col_type, notnull, dflt_value, pk = col
                parts = [f'"{name}" {col_type}']
                if pk:
                    parts.append("PRIMARY KEY")
                if notnull and not pk:
                    parts.append("NOT NULL")
                if dflt_value is not None:
                    parts.append(f"DEFAULT {dflt_value}")
                col_defs.append(" ".join(parts))

            create_sql = f'CREATE TABLE sessions_new ({", ".join(col_defs)})'

            cursor.execute(create_sql)
            cursor.execute(f"INSERT INTO sessions_new ({col_names_str}) SELECT {col_names_str} FROM sessions")
            cursor.execute("DROP TABLE sessions")
            cursor.execute("ALTER TABLE sessions_new RENAME TO sessions")

            # Recreate index on session_uuid
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_sessions_session_uuid ON sessions (session_uuid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_sessions_id ON sessions (id)")

            print("Table recreated without 'llm_temperature' column.")

        conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
