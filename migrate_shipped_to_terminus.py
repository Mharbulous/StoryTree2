#!/usr/bin/env python3
"""
Migration: Move 'shipped' from stage to terminus

This migration:
1. Recreates story_nodes table with updated CHECK constraints:
   - Stage: removes 'shipped', adds 'releasing' + legacy aliases
   - Terminus: adds 'shipped'
2. Stories with stage='shipped' -> stage='releasing', terminus='shipped'
3. Creates backup before migration

Usage: python migrate_shipped_to_terminus.py [--dry-run]
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent.parent.parent / '.claude' / 'data' / 'story-tree.db'


def find_db() -> Path:
    """Find the database path."""
    if DB_PATH.exists():
        return DB_PATH
    # Fallback: search from current directory
    cwd = Path.cwd()
    for check in [cwd, cwd.parent, cwd.parent.parent]:
        candidate = check / '.claude' / 'data' / 'story-tree.db'
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not find story-tree.db. Checked: {DB_PATH}")


def backup_database(db_path: Path) -> Path:
    """Create a timestamped backup of the database."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.with_suffix(f'.{timestamp}.bak')
    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def analyze_shipped_stories(db_path: Path) -> dict:
    """Analyze stories with stage='shipped'."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result = {
        'shipped_stories': [],
        'total_stories': 0,
        'already_terminus_shipped': [],
    }

    # Get total story count
    cursor.execute("SELECT COUNT(*) FROM story_nodes")
    result['total_stories'] = cursor.fetchone()[0]

    # Find stories with stage='shipped'
    cursor.execute("""
        SELECT id, title, stage, terminus
        FROM story_nodes
        WHERE stage = 'shipped'
    """)
    result['shipped_stories'] = cursor.fetchall()

    # Find stories already with terminus='shipped' (should be none initially)
    cursor.execute("""
        SELECT id, title, stage, terminus
        FROM story_nodes
        WHERE terminus = 'shipped'
    """)
    result['already_terminus_shipped'] = cursor.fetchall()

    conn.close()
    return result


def recreate_table_with_new_constraints(conn: sqlite3.Connection, dry_run: bool) -> None:
    """
    Recreate story_nodes table with updated CHECK constraints.

    SQLite doesn't support ALTER TABLE to modify CHECK constraints,
    so we must recreate the table:
    1. Create new table with correct schema
    2. Copy data, transforming stage='shipped' to stage='releasing', terminus='shipped'
    3. Drop old table
    4. Rename new table
    5. Recreate indexes and triggers
    """
    if dry_run:
        print("[DRY RUN] Would recreate story_nodes table with new CHECK constraints:")
        print("  - Stage: adds 'releasing' + legacy aliases, removes 'shipped'")
        print("  - Terminus: adds 'shipped'")
        return

    cursor = conn.cursor()

    # Get existing column names to handle any schema variations
    cursor.execute("PRAGMA table_info(story_nodes)")
    columns = [row[1] for row in cursor.fetchall()]

    print("Step 1: Creating new table with updated constraints...")

    # Create new table with updated schema from schema.sql
    cursor.execute("""
        CREATE TABLE story_nodes_new (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            capacity INTEGER,
            stage TEXT NOT NULL DEFAULT 'concept'
                CHECK (stage IN (
                    'concept', 'planning', 'implementing', 'testing', 'releasing',
                    'approved', 'planned', 'active', 'executing', 'reviewing', 'verifying',
                    'implemented', 'ready', 'released', 'polish'
                )),
            hold_reason TEXT DEFAULT NULL
                CHECK (hold_reason IS NULL OR hold_reason IN (
                    'queued', 'escalated', 'paused', 'blocked', 'broken', 'polish', 'conflicted', 'wishlisted'
                )),
            terminus TEXT DEFAULT NULL
                CHECK (terminus IS NULL OR terminus IN (
                    'shipped', 'rejected', 'infeasible', 'duplicative', 'legacy', 'deprecated', 'archived'
                )),
            human_review INTEGER DEFAULT 0
                CHECK (human_review IN (0, 1)),
            user_journeys TEXT,
            dependencies TEXT,
            prerequisites TEXT,
            debug_attempts INTEGER DEFAULT 0,
            project_path TEXT,
            last_implemented TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            version INTEGER DEFAULT 1,
            story TEXT,
            success_criteria TEXT
        )
    """)

    print("Step 2: Copying data and migrating shipped stories...")

    # Copy data, transforming shipped stage to releasing stage + shipped terminus
    cursor.execute("""
        INSERT INTO story_nodes_new
        (id, title, description, capacity, stage, hold_reason, terminus, human_review,
         user_journeys, dependencies, prerequisites, debug_attempts, project_path,
         last_implemented, notes, created_at, updated_at, version, story, success_criteria)
        SELECT
            id, title, description, capacity,
            CASE WHEN stage = 'shipped' THEN 'releasing' ELSE stage END,
            hold_reason,
            CASE WHEN stage = 'shipped' THEN 'shipped' ELSE terminus END,
            human_review,
            user_journeys, dependencies, prerequisites, debug_attempts, project_path,
            last_implemented, notes, created_at, datetime('now'), version, story, success_criteria
        FROM story_nodes
    """)

    migrated_count = cursor.execute(
        "SELECT COUNT(*) FROM story_nodes WHERE stage = 'shipped'"
    ).fetchone()[0]

    print(f"  Migrated {migrated_count} stories from stage='shipped' to terminus='shipped'")

    print("Step 3: Dropping old table...")
    cursor.execute("DROP TABLE story_nodes")

    print("Step 4: Renaming new table...")
    cursor.execute("ALTER TABLE story_nodes_new RENAME TO story_nodes")

    print("Step 5: Recreating indexes...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_active_pipeline ON story_nodes(stage)
            WHERE terminus IS NULL AND hold_reason IS NULL
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_held_stories ON story_nodes(hold_reason)
            WHERE hold_reason IS NOT NULL
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_terminal_stories ON story_nodes(terminus)
            WHERE terminus IS NOT NULL
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_needs_review ON story_nodes(human_review)
            WHERE human_review = 1
    """)

    print("Step 6: Recreating trigger...")
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS story_nodes_updated_at
        AFTER UPDATE ON story_nodes
        FOR EACH ROW
        BEGIN
            UPDATE story_nodes SET updated_at = datetime('now') WHERE id = OLD.id;
        END
    """)

    conn.commit()
    print("Schema migration complete.")




def main():
    parser = argparse.ArgumentParser(
        description="Migrate 'shipped' from stage to terminus"
    )
    parser.add_argument(
        '--db', type=Path, default=None,
        help='Path to story-tree.db (auto-detected if not specified)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    try:
        db_path = args.db or find_db()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    print(f"Database: {db_path}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Analyze current state
    analysis = analyze_shipped_stories(db_path)

    print("Current state:")
    print(f"  Total stories: {analysis['total_stories']}")
    print(f"  Stories with stage='shipped': {len(analysis['shipped_stories'])}")
    print(f"  Stories with terminus='shipped': {len(analysis['already_terminus_shipped'])}")
    print()

    if analysis['already_terminus_shipped']:
        print("Stories already with terminus='shipped':")
        for story in analysis['already_terminus_shipped']:
            print(f"  - {story[0]}: {story[1]} (stage={story[2]})")
        print()

    count = len(analysis['shipped_stories'])

    if count == 0:
        print("No stories with stage='shipped' to migrate.")
        return 0

    print(f"Found {count} stories to migrate:")
    for story in analysis['shipped_stories']:
        print(f"  - {story[0]}: {story[1]}")
    print()

    # Create backup (only for live runs)
    if not args.dry_run:
        backup_database(db_path)

    # Connect and migrate
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # This recreates the table with new schema AND migrates data in one step
        recreate_table_with_new_constraints(conn, args.dry_run)

        if not args.dry_run:
            print()
            print("=" * 50)
            print("Migration Summary")
            print("=" * 50)
            print(f"Stories updated: {count}")
            print("  stage: 'shipped' -> 'releasing'")
            print("  terminus: NULL -> 'shipped'")
            print()
            print("Schema updated:")
            print("  - Stage CHECK: added 'releasing' + legacy aliases, removed 'shipped'")
            print("  - Terminus CHECK: added 'shipped'")

        return 0
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    exit(main())
