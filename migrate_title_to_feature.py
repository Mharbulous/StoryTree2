#!/usr/bin/env python3
"""
Migrate story_nodes table: rename 'title' column to 'feature'.

This script aligns the database schema with the codebase terminology by
renaming the 'title' column to 'feature' in the story_nodes table.

Usage:
    python .storytree/gui/migrate_title_to_feature.py           # Run migration
    python .storytree/gui/migrate_title_to_feature.py --dry-run # Preview only
    python .storytree/gui/migrate_title_to_feature.py --verify  # Check results
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent.parent / '.claude' / 'data' / 'story-tree.db'


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


def check_column_exists(db_path: Path, column_name: str) -> bool:
    """Check if a column exists in story_nodes table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(story_nodes)")
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    return column_name in columns


def migrate(db_path: Path, dry_run: bool = False) -> dict:
    """
    Migrate database: rename 'title' column to 'feature'.

    Returns:
        dict with migration statistics
    """
    stats = {
        'column_renamed': False,
        'backup_path': None,
        'rows_migrated': 0,
    }

    print(f"Database: {db_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    # Check current state
    has_title = check_column_exists(db_path, 'title')
    has_feature = check_column_exists(db_path, 'feature')

    print(f"Column 'title' exists: {has_title}")
    print(f"Column 'feature' exists: {has_feature}")
    print()

    if has_feature and not has_title:
        print("Migration already complete. Column 'feature' exists.")
        return stats

    if not has_title:
        print("ERROR: Column 'title' not found. Cannot migrate.")
        return stats

    if has_feature and has_title:
        print("WARNING: Both 'title' and 'feature' columns exist. Manual intervention needed.")
        return stats

    if dry_run:
        print("[DRY RUN] Would perform the following:")
        print("  - Create backup of database")
        print("  - Create new table with 'feature' column instead of 'title'")
        print("  - Copy all data from old table to new table")
        print("  - Drop old table and rename new table")
        print("  - Recreate indexes and triggers")
        return stats

    # Create backup
    backup_path = db_path.with_suffix(f'.db.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}')
    shutil.copy2(db_path, backup_path)
    stats['backup_path'] = str(backup_path)
    print(f"Created backup: {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get row count
    cursor.execute("SELECT COUNT(*) FROM story_nodes")
    stats['rows_migrated'] = cursor.fetchone()[0]
    print(f"Rows to migrate: {stats['rows_migrated']}")

    # Step 1: Create new table with 'feature' column
    print("\nStep 1: Creating new table with 'feature' column...")
    cursor.execute("DROP TABLE IF EXISTS story_nodes_new")

    # Get current schema to preserve it
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='story_nodes'")
    old_schema = cursor.fetchone()[0]

    # Create new schema with 'feature' instead of 'title'
    new_schema = old_schema.replace('story_nodes', 'story_nodes_new', 1)
    new_schema = new_schema.replace('title TEXT NOT NULL', 'feature TEXT NOT NULL')

    cursor.executescript(new_schema)
    print("  New table created")

    # Step 2: Get column list from old table (excluding 'title')
    cursor.execute("PRAGMA table_info(story_nodes)")
    columns = [row[1] for row in cursor.fetchall()]

    # Build column lists for INSERT
    old_columns = ', '.join(columns)
    new_columns = old_columns.replace('title', 'feature')

    # Step 3: Copy data
    print("\nStep 2: Copying data to new table...")
    cursor.execute(f"""
        INSERT INTO story_nodes_new ({new_columns})
        SELECT {old_columns}
        FROM story_nodes
    """)
    print(f"  Copied {stats['rows_migrated']} rows")

    # Step 4: Drop old table and rename new
    print("\nStep 3: Replacing old table with new...")
    cursor.execute("DROP TABLE story_nodes")
    cursor.execute("ALTER TABLE story_nodes_new RENAME TO story_nodes")
    stats['column_renamed'] = True
    print("  Table replaced")

    # Step 5: Recreate indexes
    print("\nStep 4: Recreating indexes...")
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_active_pipeline ON story_nodes(stage)
            WHERE terminus IS NULL AND hold_reason IS NULL;
        CREATE INDEX IF NOT EXISTS idx_held_stories ON story_nodes(hold_reason)
            WHERE hold_reason IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_terminal_stories ON story_nodes(terminus)
            WHERE terminus IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_needs_review ON story_nodes(human_review)
            WHERE human_review = 1;
    """)
    # Create story_key index only if column exists
    if check_column_exists(db_path, 'story_key'):
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_story_key ON story_nodes(story_key)")
    print("  Indexes recreated")

    # Step 6: Recreate trigger (using appropriate primary key column)
    print("\nStep 5: Recreating trigger...")
    pk_column = 'story_path' if check_column_exists(db_path, 'story_path') else 'id'
    cursor.execute("DROP TRIGGER IF EXISTS story_nodes_updated_at")
    cursor.execute(f"""
        CREATE TRIGGER story_nodes_updated_at
        AFTER UPDATE ON story_nodes
        FOR EACH ROW
        BEGIN
            UPDATE story_nodes SET updated_at = datetime('now') WHERE {pk_column} = OLD.{pk_column};
        END
    """)
    print("  Trigger recreated")

    # Step 7: Update metadata
    print("\nStep 6: Updating metadata...")
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('last_migration', ?)
    """, (datetime.now().isoformat(),))
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('migration_note', 'Renamed title column to feature')
    """)
    print("  Metadata updated")

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
    has_title = check_column_exists(db_path, 'title')
    has_feature = check_column_exists(db_path, 'feature')

    print("\nColumn check:")
    if has_feature and not has_title:
        print("  [OK] 'feature' column exists, 'title' column removed")
    elif has_title and not has_feature:
        print("  [FAIL] Migration not applied - 'title' still exists")
        success = False
    elif has_title and has_feature:
        print("  [WARN] Both columns exist - migration incomplete")
        success = False
    else:
        print("  [FAIL] Neither column exists - data may be corrupted")
        success = False

    # Check data integrity
    print("\nData integrity:")
    cursor.execute("SELECT COUNT(*) FROM story_nodes")
    count = cursor.fetchone()[0]
    print(f"  Row count: {count}")

    cursor.execute("SELECT COUNT(*) FROM story_nodes WHERE feature IS NULL OR feature = ''")
    empty_count = cursor.fetchone()[0]
    if empty_count > 0:
        print(f"  [WARN] {empty_count} rows have empty/null feature")
    else:
        print("  [OK] All rows have feature values")

    # Check metadata
    print("\nMetadata:")
    cursor.execute("SELECT key, value FROM metadata WHERE key IN ('last_migration', 'migration_note')")
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
        description="Migrate story_nodes table: rename 'title' column to 'feature'"
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

    if not args.dry_run and stats['column_renamed']:
        print("\n" + "=" * 50)
        print("Migration Summary")
        print("=" * 50)
        print(f"Rows migrated: {stats['rows_migrated']}")
        print(f"Column renamed: title → feature")
        if stats['backup_path']:
            print(f"Backup: {stats['backup_path']}")
        print()

        verify(db_path)

    return 0


if __name__ == '__main__':
    exit(main())
