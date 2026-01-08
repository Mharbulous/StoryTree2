#!/usr/bin/env python3
"""
Migrate story-tree.db data to use updated terminology.

This script updates existing data values to match the new terminology:

Stage mappings:
- executing → implementing
- implemented → shipped
- ready → shipped
- reviewing → testing
- verifying → testing
(concept, planning remain unchanged)

Hold_reason mappings:
- conflict → conflicted
- wishlist → wishlisted
(blocked, queued, paused, broken, polish remain unchanged)

Usage:
    python dev-tools/xstory/migrate_terminology_update.py           # Run migration
    python dev-tools/xstory/migrate_terminology_update.py --dry-run # Preview only
    python dev-tools/xstory/migrate_terminology_update.py --verify  # Check results
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent.parent.parent / '.claude' / 'data' / 'story-tree.db'

# Stage value mappings (old → new)
STAGE_MAPPINGS = {
    'executing': 'implementing',
    'implemented': 'shipped',
    'ready': 'shipped',
    'reviewing': 'testing',
    'verifying': 'testing',
    # These remain unchanged:
    # 'concept': 'concept',
    # 'planning': 'planning',
}

# Hold_reason value mappings (old → new)
HOLD_REASON_MAPPINGS = {
    'conflict': 'conflicted',
    'wishlist': 'wishlisted',
    # These remain unchanged:
    # 'blocked': 'blocked',
    # 'queued': 'queued',
    # 'paused': 'paused',
    # 'broken': 'broken',
    # 'polish': 'polish',
}

# New schema with updated CHECK constraints for new terminology
NEW_STORY_NODES_SCHEMA = """
CREATE TABLE story_nodes_new (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    capacity INTEGER,
    stage TEXT NOT NULL DEFAULT 'concept'
        CHECK (stage IN (
            'concept', 'planning', 'implementing',
            'testing', 'shipped'
        )),
    hold_reason TEXT DEFAULT NULL
        CHECK (hold_reason IS NULL OR hold_reason IN (
            'queued', 'escalated', 'paused', 'blocked', 'broken', 'polish', 'conflicted', 'wishlisted'
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


def analyze_current_data(db_path: Path) -> dict:
    """Analyze current database data to determine what needs migration."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result = {
        'total_rows': 0,
        'stage_counts': {},
        'hold_reason_counts': {},
        'stage_migrations_needed': {},
        'hold_reason_migrations_needed': {},
    }

    # Get total row count
    cursor.execute("SELECT COUNT(*) FROM story_nodes")
    result['total_rows'] = cursor.fetchone()[0]

    # Get stage distribution
    cursor.execute("SELECT stage, COUNT(*) FROM story_nodes GROUP BY stage")
    for value, count in cursor.fetchall():
        result['stage_counts'][value or 'NULL'] = count
        if value in STAGE_MAPPINGS:
            result['stage_migrations_needed'][value] = count

    # Get hold_reason distribution
    cursor.execute("SELECT hold_reason, COUNT(*) FROM story_nodes GROUP BY hold_reason")
    for value, count in cursor.fetchall():
        result['hold_reason_counts'][value or 'NULL'] = count
        if value in HOLD_REASON_MAPPINGS:
            result['hold_reason_migrations_needed'][value] = count

    conn.close()
    return result


def migrate(db_path: Path, dry_run: bool = False) -> dict:
    """
    Migrate database: update stage and hold_reason values to new terminology.

    Uses CREATE-COPY-RENAME pattern to update schema and values simultaneously.

    Returns:
        dict with migration statistics
    """
    stats = {
        'stage_updates': 0,
        'hold_reason_updates': 0,
        'total_rows_migrated': 0,
        'backup_path': None,
        'schema_updated': False,
    }

    analysis = analyze_current_data(db_path)

    print(f"Database: {db_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    # Show current state
    print("Current state:")
    print(f"  Total rows: {analysis['total_rows']}")
    print()

    print("Current STAGE distribution:")
    for value, count in sorted(analysis['stage_counts'].items()):
        migration_note = f" → {STAGE_MAPPINGS[value]}" if value in STAGE_MAPPINGS else ""
        print(f"  {value}: {count}{migration_note}")
    print()

    print("Current HOLD_REASON distribution:")
    for value, count in sorted(analysis['hold_reason_counts'].items()):
        migration_note = f" → {HOLD_REASON_MAPPINGS[value]}" if value in HOLD_REASON_MAPPINGS else ""
        print(f"  {value}: {count}{migration_note}")
    print()

    # Check if migration is needed
    if not analysis['stage_migrations_needed'] and not analysis['hold_reason_migrations_needed']:
        print("No data migration needed. All values already use new terminology.")
        return stats

    if dry_run:
        print("[DRY RUN] Would perform the following updates:")
        if analysis['stage_migrations_needed']:
            print("\nStage updates:")
            for old_val, count in analysis['stage_migrations_needed'].items():
                print(f"  {old_val} → {STAGE_MAPPINGS[old_val]}: {count} rows")
        if analysis['hold_reason_migrations_needed']:
            print("\nHold_reason updates:")
            for old_val, count in analysis['hold_reason_migrations_needed'].items():
                print(f"  {old_val} → {HOLD_REASON_MAPPINGS[old_val]}: {count} rows")
        total_affected = sum(analysis['stage_migrations_needed'].values()) + sum(analysis['hold_reason_migrations_needed'].values())
        print(f"\nTotal rows affected: {total_affected}")
        print(f"\nWould also update schema CHECK constraints to new values")
        return stats

    # Create backup
    backup_path = db_path.with_suffix(f'.db.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}')
    shutil.copy2(db_path, backup_path)
    stats['backup_path'] = str(backup_path)
    print(f"Created backup: {backup_path}\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Step 1: Create new table with updated schema
    print("Step 1: Creating new table with updated CHECK constraints...")
    cursor.execute("DROP TABLE IF EXISTS story_nodes_new")
    cursor.executescript(NEW_STORY_NODES_SCHEMA)

    # Step 2: Copy all data with value transformations
    print("\nStep 2: Migrating data with terminology updates...")
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
            id, title, description, capacity,
            CASE stage
                WHEN 'executing' THEN 'implementing'
                WHEN 'implemented' THEN 'shipped'
                WHEN 'ready' THEN 'shipped'
                WHEN 'reviewing' THEN 'testing'
                WHEN 'verifying' THEN 'testing'
                ELSE stage
            END as stage,
            CASE hold_reason
                WHEN 'conflict' THEN 'conflicted'
                WHEN 'wishlist' THEN 'wishlisted'
                ELSE hold_reason
            END as hold_reason,
            terminus, human_review,
            project_path, last_implemented, notes,
            created_at, updated_at, version,
            story, success_criteria, dependencies, prerequisites,
            debug_attempts, user_journeys
        FROM story_nodes
    """)
    stats['total_rows_migrated'] = cursor.rowcount
    print(f"  Migrated {stats['total_rows_migrated']} rows")

    # Count actual transformations
    for old_val in STAGE_MAPPINGS.keys():
        stats['stage_updates'] += analysis['stage_migrations_needed'].get(old_val, 0)
    for old_val in HOLD_REASON_MAPPINGS.keys():
        stats['hold_reason_updates'] += analysis['hold_reason_migrations_needed'].get(old_val, 0)

    # Step 3: Drop old table and rename new
    print("\nStep 3: Replacing old table with new...")
    cursor.execute("DROP TABLE story_nodes")
    cursor.execute("ALTER TABLE story_nodes_new RENAME TO story_nodes")
    stats['schema_updated'] = True
    print("  Schema updated with new CHECK constraints")

    # Step 4: Recreate indexes
    print("\nStep 4: Recreating indexes...")
    cursor.executescript("""
        DROP INDEX IF EXISTS idx_active_pipeline;
        DROP INDEX IF EXISTS idx_held_stories;
        DROP INDEX IF EXISTS idx_terminal_stories;
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
    print("  Indexes recreated")

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
        VALUES ('last_migration', ?)
    """, (datetime.now().isoformat(),))
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('migration_note', 'Updated stage and hold_reason values and CHECK constraints to new terminology')
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

    # Check for old stage values
    print("\nStage values verification:")
    cursor.execute("""
        SELECT stage, COUNT(*)
        FROM story_nodes
        WHERE stage IN ('executing', 'implemented', 'ready', 'reviewing', 'verifying')
        GROUP BY stage
    """)
    old_stages = cursor.fetchall()
    if old_stages:
        print("  [ERROR] Found old stage values:")
        for value, count in old_stages:
            print(f"    {value}: {count}")
        success = False
    else:
        print("  [OK] No old stage values found")

    # Check for old hold_reason values
    print("\nHold_reason values verification:")
    cursor.execute("""
        SELECT hold_reason, COUNT(*)
        FROM story_nodes
        WHERE hold_reason IN ('conflict', 'wishlist')
        GROUP BY hold_reason
    """)
    old_holds = cursor.fetchall()
    if old_holds:
        print("  [ERROR] Found old hold_reason values:")
        for value, count in old_holds:
            print(f"    {value}: {count}")
        success = False
    else:
        print("  [OK] No old hold_reason values found")

    # Show current distribution
    print("\nCurrent STAGE distribution:")
    cursor.execute("SELECT stage, COUNT(*) FROM story_nodes GROUP BY stage ORDER BY stage")
    for value, count in cursor.fetchall():
        print(f"  {value or 'NULL'}: {count}")

    print("\nCurrent HOLD_REASON distribution:")
    cursor.execute("SELECT hold_reason, COUNT(*) FROM story_nodes GROUP BY hold_reason ORDER BY hold_reason")
    for value, count in cursor.fetchall():
        print(f"  {value or 'NULL'}: {count}")

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
        description="Migrate story-tree.db data to use updated terminology"
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
        print(f"Total rows migrated: {stats['total_rows_migrated']}")
        print(f"Stage values updated: {stats['stage_updates']}")
        print(f"Hold_reason values updated: {stats['hold_reason_updates']}")
        print(f"Schema updated: Yes (CHECK constraints updated)")
        if stats['backup_path']:
            print(f"Backup: {stats['backup_path']}")
        print()

        verify(db_path)

    return 0


if __name__ == '__main__':
    exit(main())
