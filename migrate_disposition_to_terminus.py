#!/usr/bin/env python3
"""
Migrate story-tree.db: Rename 'disposition' column to 'terminus'.

This script completes the terminology migration from 'disposition' to 'terminus'
for the three-field workflow system. The column values remain unchanged:
- rejected, infeasible, duplicative, legacy, deprecated, archived

Uses the CREATE-COPY-RENAME pattern since SQLite doesn't support direct
column rename on tables with CHECK constraints.

Usage:
    python dev-tools/xstory/migrate_disposition_to_terminus.py           # Run migration
    python dev-tools/xstory/migrate_disposition_to_terminus.py --dry-run # Preview only
    python dev-tools/xstory/migrate_disposition_to_terminus.py --verify  # Check results
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent.parent.parent / '.claude' / 'data' / 'story-tree.db'

# New schema with 'terminus' column instead of 'disposition'
# Matches current v4.0 schema exactly, only renaming disposition -> terminus
NEW_STORY_NODES_SCHEMA = """
CREATE TABLE story_nodes_new (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    capacity INTEGER,
    stage TEXT NOT NULL DEFAULT 'concept'
        CHECK (stage IN (
            'concept', 'planning', 'executing',
            'reviewing', 'verifying', 'implemented', 'ready', 'released'
        )),
    hold_reason TEXT DEFAULT NULL
        CHECK (hold_reason IS NULL OR hold_reason IN (
            'queued', 'pending', 'paused', 'blocked', 'broken', 'polish', 'conflict', 'wishlist'
        )),
    terminus TEXT DEFAULT NULL
        CHECK (terminus IS NULL OR terminus IN (
            'rejected', 'infeasible', 'duplicative', 'legacy', 'deprecated', 'archived'
        )),
    human_review INTEGER DEFAULT 0
        CHECK (human_review IN (0, 1)),
    project_path TEXT,
    last_implemented TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER DEFAULT 1,
    story TEXT,
    success_criteria TEXT,
    dependencies TEXT,
    prerequisites TEXT,
    debug_attempts INTEGER DEFAULT 0,
    user_journeys TEXT
);
"""


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


def analyze_current_schema(db_path: Path) -> dict:
    """Analyze current database schema and data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result = {
        'has_disposition_column': False,
        'has_terminus_column': False,
        'terminus_values': {},
        'total_rows': 0,
        'needs_migration': False,
    }

    # Check column names
    cursor.execute("PRAGMA table_info(story_nodes)")
    columns = {row[1] for row in cursor.fetchall()}
    result['has_disposition_column'] = 'disposition' in columns
    result['has_terminus_column'] = 'terminus' in columns

    # Get total row count
    cursor.execute("SELECT COUNT(*) FROM story_nodes")
    result['total_rows'] = cursor.fetchone()[0]

    # Get current terminus/disposition distribution
    if result['has_disposition_column']:
        cursor.execute("""
            SELECT disposition, COUNT(*)
            FROM story_nodes
            GROUP BY disposition
        """)
        for value, count in cursor.fetchall():
            result['terminus_values'][value or 'NULL'] = count
        result['needs_migration'] = True
    elif result['has_terminus_column']:
        cursor.execute("""
            SELECT terminus, COUNT(*)
            FROM story_nodes
            GROUP BY terminus
        """)
        for value, count in cursor.fetchall():
            result['terminus_values'][value or 'NULL'] = count
        result['needs_migration'] = False

    conn.close()
    return result


def migrate(db_path: Path, dry_run: bool = False) -> dict:
    """
    Migrate database: rename 'disposition' column to 'terminus'.

    Returns:
        dict with migration statistics
    """
    stats = {
        'rows_migrated': 0,
        'schema_updated': False,
        'backup_path': None,
        'version_updated': False,
    }

    analysis = analyze_current_schema(db_path)

    print(f"Database: {db_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    # Show current state
    print("Current state:")
    print(f"  Has 'disposition' column: {analysis['has_disposition_column']}")
    print(f"  Has 'terminus' column: {analysis['has_terminus_column']}")
    print(f"  Total rows: {analysis['total_rows']}")
    print()

    print("Current terminus/disposition distribution:")
    for value, count in sorted(analysis['terminus_values'].items()):
        print(f"  {value}: {count}")
    print()

    if not analysis['needs_migration']:
        if analysis['has_terminus_column']:
            print("Database already has 'terminus' column. No migration needed.")
        else:
            print("ERROR: Database has neither 'disposition' nor 'terminus' column!")
        return stats

    if dry_run:
        print("[DRY RUN] Would perform the following:")
        print(f"  - Rename column 'disposition' to 'terminus'")
        print(f"  - Migrate {analysis['total_rows']} rows")
        print(f"  - Rename index 'idx_disposed_stories' to 'idx_terminal_stories'")
        print(f"  - Update schema version to 4.2.0")
        return stats

    # Create backup
    backup_path = db_path.with_suffix(f'.db.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}')
    shutil.copy2(db_path, backup_path)
    stats['backup_path'] = str(backup_path)
    print(f"Created backup: {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Step 1: Create new table with 'terminus' column
    print("\nStep 1: Creating new table with 'terminus' column...")
    cursor.execute("DROP TABLE IF EXISTS story_nodes_new")
    cursor.executescript(NEW_STORY_NODES_SCHEMA)

    # Step 2: Copy all data, renaming disposition to terminus
    print("\nStep 2: Migrating data (disposition to terminus)...")
    cursor.execute("""
        INSERT INTO story_nodes_new (
            id, title, description, capacity, stage,
            hold_reason, terminus, human_review,
            project_path, last_implemented, notes,
            created_at, updated_at, version,
            story, success_criteria, dependencies, prerequisites,
            debug_attempts, user_journeys
        )
        SELECT
            id, title, description, capacity, stage,
            hold_reason, disposition, human_review,
            project_path, last_implemented, notes,
            created_at, updated_at, version,
            story, success_criteria, dependencies, prerequisites,
            debug_attempts, user_journeys
        FROM story_nodes
    """)
    stats['rows_migrated'] = cursor.rowcount
    print(f"  Migrated {stats['rows_migrated']} rows")

    # Step 3: Drop old table and rename new
    print("\nStep 3: Replacing old table with new...")
    cursor.execute("DROP TABLE story_nodes")
    cursor.execute("ALTER TABLE story_nodes_new RENAME TO story_nodes")
    stats['schema_updated'] = True
    print("  Column renamed: disposition to terminus")

    # Step 4: Recreate indexes with new names
    print("\nStep 4: Recreating indexes...")
    cursor.executescript("""
        DROP INDEX IF EXISTS idx_disposed_stories;
        DROP INDEX IF EXISTS idx_active_pipeline;
        DROP INDEX IF EXISTS idx_held_stories;
        DROP INDEX IF EXISTS idx_needs_review;

        CREATE INDEX IF NOT EXISTS idx_active_pipeline ON story_nodes(stage)
            WHERE terminus IS NULL AND hold_reason IS NULL;
        CREATE INDEX IF NOT EXISTS idx_held_stories ON story_nodes(hold_reason)
            WHERE hold_reason IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_terminal_stories ON story_nodes(terminus)
            WHERE terminus IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_needs_review ON story_nodes(human_review)
            WHERE human_review = 1;
    """)
    print("  Indexes recreated (idx_disposed_stories to idx_terminal_stories)")

    # Step 5: Recreate trigger
    print("\nStep 5: Recreating trigger...")
    cursor.executescript("""
        DROP TRIGGER IF EXISTS story_nodes_updated_at;
        CREATE TRIGGER story_nodes_updated_at
        AFTER UPDATE ON story_nodes
        FOR EACH ROW
        BEGIN
            UPDATE story_nodes SET updated_at = datetime('now') WHERE id = OLD.id;
        END;
    """)
    print("  Trigger recreated")

    # Step 6: Update metadata
    print("\nStep 6: Updating metadata...")
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('schema_version', '4.2.0')
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('last_migration', ?)
    """, (datetime.now().isoformat(),))
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('migration_note', 'Renamed disposition column to terminus (terminology migration)')
    """)
    stats['version_updated'] = True
    print("  Schema version updated to 4.2.0")

    conn.commit()
    conn.close()

    return stats


def verify(db_path: Path) -> bool:
    """Verify the migration was successful."""
    print(f"\nVerifying migration: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    success = True

    # Check columns
    print("\nColumn verification:")
    cursor.execute("PRAGMA table_info(story_nodes)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'terminus' in columns:
        print("  [OK] 'terminus' column exists")
    else:
        print("  [ERROR] 'terminus' column missing")
        success = False

    if 'disposition' in columns:
        print("  [ERROR] 'disposition' column still exists (should be renamed)")
        success = False
    else:
        print("  [OK] 'disposition' column removed")

    # Check schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='story_nodes'")
    schema = cursor.fetchone()[0]

    print("\nSchema CHECK constraints:")
    if "terminus TEXT" in schema:
        print("  [OK] terminus column in schema")
    else:
        print("  [WARN] terminus column definition not found")
        success = False

    if "disposition" in schema.lower():
        print("  [ERROR] 'disposition' still referenced in schema")
        success = False

    # Check indexes
    print("\nIndex verification:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='story_nodes'")
    indexes = {row[0] for row in cursor.fetchall()}

    if 'idx_terminal_stories' in indexes:
        print("  [OK] idx_terminal_stories exists")
    else:
        print("  [WARN] idx_terminal_stories not found")

    if 'idx_disposed_stories' in indexes:
        print("  [ERROR] idx_disposed_stories still exists (should be renamed)")
        success = False
    else:
        print("  [OK] idx_disposed_stories removed")

    # Show terminus distribution
    print("\nCurrent terminus distribution:")
    cursor.execute("""
        SELECT terminus, COUNT(*)
        FROM story_nodes
        GROUP BY terminus
        ORDER BY terminus
    """)
    for value, count in cursor.fetchall():
        print(f"  {value or 'NULL'}: {count}")

    # Check metadata
    print("\nMetadata:")
    cursor.execute("SELECT key, value FROM metadata WHERE key IN ('schema_version', 'last_migration', 'migration_note')")
    for key, value in cursor.fetchall():
        print(f"  {key}: {value}")

    conn.close()

    print()
    if success:
        print("[SUCCESS] Migration verified successfully")
    else:
        print("[FAILED] Migration verification found issues")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Migrate story-tree.db: Rename 'disposition' column to 'terminus'"
    )
    parser.add_argument(
        '--db', type=Path, default=None,
        help='Path to story-tree.db (auto-detected if not specified)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be changed without making changes'
    )
    parser.add_argument(
        '--verify', action='store_true',
        help='Verify migration results only'
    )

    args = parser.parse_args()

    try:
        db_path = args.db or find_db()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    if args.verify:
        return 0 if verify(db_path) else 1

    stats = migrate(db_path, dry_run=args.dry_run)

    if not args.dry_run and stats['schema_updated']:
        print("\n" + "=" * 50)
        print("Migration Summary")
        print("=" * 50)
        print(f"Rows migrated: {stats['rows_migrated']}")
        print(f"Column renamed: disposition to terminus")
        print(f"Index renamed: idx_disposed_stories to idx_terminal_stories")
        print(f"Schema version: 4.2.0")
        if stats['backup_path']:
            print(f"Backup: {stats['backup_path']}")
        print()

        verify(db_path)

    return 0


if __name__ == '__main__':
    exit(main())
