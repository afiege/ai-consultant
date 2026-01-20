"""
Migration script to add six_three_five_skipped column to sessions table.

Run this script once to update your existing database:
    python migrate_add_skip_field.py
"""

import sqlite3
import os

# Database path
DB_PATH = "./database/ai_consultant.db"

def migrate():
    """Add six_three_five_skipped column if it doesn't exist."""

    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("The column will be created when you first start the server.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'six_three_five_skipped' in columns:
            print("✓ Column 'six_three_five_skipped' already exists in sessions table")
        else:
            # Add the column with default value False
            cursor.execute("""
                ALTER TABLE sessions
                ADD COLUMN six_three_five_skipped BOOLEAN DEFAULT 0
            """)
            conn.commit()
            print("✓ Successfully added 'six_three_five_skipped' column to sessions table")

    except sqlite3.Error as e:
        print(f"✗ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("Running migration: Add six_three_five_skipped column")
    migrate()
    print("Migration complete!")
