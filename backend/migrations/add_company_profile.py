#!/usr/bin/env python3
"""
Migration script to add company_profile column to sessions table.

Run this script to add the new column to an existing database:
    python migrations/add_company_profile.py

This is safe to run multiple times - it checks if the column exists first.
"""

import sqlite3
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def migrate():
    """Add company_profile column to sessions table if it doesn't exist."""
    # Get database path from settings
    db_path = settings.database_url.replace("sqlite:///", "")

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("The column will be created automatically when you start the app.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]

        if "company_profile" in columns:
            print("Column 'company_profile' already exists in sessions table.")
            return

        # Add the column
        print("Adding 'company_profile' column to sessions table...")
        cursor.execute("""
            ALTER TABLE sessions
            ADD COLUMN company_profile TEXT
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
