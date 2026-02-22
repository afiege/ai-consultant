#!/usr/bin/env python3
"""
Migration script to add llm_temperature column to sessions table.

Run this script to add the new column to an existing database:
    python migrations/add_llm_temperature.py

This is safe to run multiple times - it checks if the column exists first.
"""

import sqlite3
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def migrate():
    """Add llm_temperature column to sessions table if it doesn't exist."""
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

        if "llm_temperature" in columns:
            print("Column 'llm_temperature' already exists in sessions table.")
            return

        print("Adding 'llm_temperature' column to sessions table...")
        cursor.execute("""
            ALTER TABLE sessions
            ADD COLUMN llm_temperature REAL
        """)

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
