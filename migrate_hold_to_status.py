#!/usr/bin/env python
"""Migration: Rename hold_reason to status in story_nodes table.

This migration:
1. Renames hold_reason column to status
2. Updates NULL values to 'ready' (explicit status)
3. Updates index names
"""

import re
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / 'data' / 'story-tree.db'


def backup_database():
    """Create timestamped backup before migration."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = DB_PATH.with_suffix(f'.backup_{timestamp}.db')
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def migrate():
    """Execute the migration."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return False

    backup_database()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if migration already applied
    cursor.execute("PRAGMA table_info(story_nodes)")
    columns = {row[1]: row for row in cursor.fetchall()}

    if 'status' in columns:
        print("Migration already applied (status column exists)")
        conn.close()
        return True

    if 'hold_reason' not in columns:
        print("Error: hold_reason column not found")
        conn.close()
        return False

    print("Starting migration: hold_reason -> status")

    # Get actual column names in order
    cursor.execute("PRAGMA table_info(story_nodes)")
    column_info = cursor.fetchall()
    column_names = [col[1] for col in column_info]

    # Build the new column list (replacing hold_reason with status)
    new_columns = []
    select_columns = []
    for col in column_names:
        if col == 'hold_reason':
            new_columns.append('status')
            select_columns.append("COALESCE(hold_reason, 'ready') as status")
        else:
            new_columns.append(col)
            select_columns.append(col)

    # Get the CREATE TABLE statement to understand column definitions
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='story_nodes'")
    original_create = cursor.fetchone()[0]

    # Build new CREATE TABLE by replacing hold_reason with status
    new_create = original_create.replace('hold_reason', 'status')
    # Also update the default from NULL to 'ready'
    new_create = new_create.replace("status TEXT DEFAULT NULL", "status TEXT DEFAULT 'ready'")
    # Update CHECK constraint - remove "IS NULL OR" and add 'ready' to the status check
    new_create = new_create.replace("status IS NULL OR ", "")
    # Add 'ready' to the status CHECK constraint
    # The status IN check looks like: CHECK (status IN ('queued', ...))
    # We need to add 'ready' to this list
    # Find and replace the status CHECK constraint
    status_check_pattern = r"(CHECK\s*\(\s*status\s+IN\s*\()"
    new_create = re.sub(status_check_pattern, r"\1'ready', ", new_create)
    # Change table name to _new (handle quoted and unquoted versions)
    new_create = new_create.replace('CREATE TABLE "story_nodes"', 'CREATE TABLE "story_nodes_new"', 1)
    new_create = new_create.replace('CREATE TABLE story_nodes', 'CREATE TABLE story_nodes_new', 1)

    print(f"Creating new table structure...")

    try:
        # Drop any leftover temp table from previous failed migration
        cursor.execute("DROP TABLE IF EXISTS story_nodes_new")

        # Create new table
        cursor.execute(new_create)

        # Copy data
        insert_sql = f"""
            INSERT INTO story_nodes_new ({', '.join(new_columns)})
            SELECT {', '.join(select_columns)}
            FROM story_nodes
        """
        cursor.execute(insert_sql)

        # Drop old table
        cursor.execute("DROP TABLE story_nodes")

        # Rename new table
        cursor.execute("ALTER TABLE story_nodes_new RENAME TO story_nodes")

        # Drop old indexes (they reference old column name)
        cursor.execute("DROP INDEX IF EXISTS idx_active_pipeline")
        cursor.execute("DROP INDEX IF EXISTS idx_held_stories")

        # Recreate indexes with updated logic
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_active_pipeline ON story_nodes(stage)
            WHERE terminus IS NULL AND status = 'ready'
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON story_nodes(status)
            WHERE status != 'ready'
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_terminal_stories ON story_nodes(terminus)
            WHERE terminus IS NOT NULL
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_needs_review ON story_nodes(human_review)
            WHERE human_review = 1
        """)

        conn.commit()

    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
        conn.close()
        return False

    # Verify migration
    cursor.execute("PRAGMA table_info(story_nodes)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'status' in columns and 'hold_reason' not in columns:
        print("Migration successful!")
        cursor.execute("SELECT COUNT(*) FROM story_nodes WHERE status = 'ready'")
        ready_count = cursor.fetchone()[0]
        print(f"Stories with status='ready': {ready_count}")
        cursor.execute("SELECT COUNT(*) FROM story_nodes")
        total_count = cursor.fetchone()[0]
        print(f"Total stories: {total_count}")
        conn.close()
        return True
    else:
        print("Migration verification failed")
        conn.close()
        return False


if __name__ == '__main__':
    import sys
    success = migrate()
    sys.exit(0 if success else 1)
