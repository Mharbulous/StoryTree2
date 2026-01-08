#!/usr/bin/env python3
"""
Migrate SyncoPaid story-tree.db to canonical v4.0 three-field schema.

This script aligns the SyncoPaid database with the canonical schema by:
1. Renaming hold_reason values to match canonical naming:
   - escalated → queued (semantic equivalent: both mean waiting)
   - conflicted → conflict (spelling fix)
   - wishlisted → wishlist (spelling fix)
2. Updating CHECK constraints to match canonical schema

Canonical v4.0 schema (from workflow-three-field-model.md):
- stage: concept, planning, executing, reviewing, verifying,
         implemented, ready, released (gerunds for ongoing processes)
- hold_reason: queued, pending, paused, blocked, broken, polish, conflict, wishlist
- disposition: rejected, infeasible, duplicative, legacy, deprecated, archived

Usage:
    python dev-tools/xstory/migrate_to_canonical_schema.py           # Run migration
    python dev-tools/xstory/migrate_to_canonical_schema.py --dry-run # Preview only
    python dev-tools/xstory/migrate_to_canonical_schema.py --verify  # Check results
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent.parent.parent / '.claude' / 'data' / 'story-tree.db'

# Mapping of old hold_reason values to canonical values
HOLD_REASON_MAPPING = {
    'escalated': 'queued',    # Semantic match: both mean waiting/queued
    'conflicted': 'conflict', # Spelling normalization
    'wishlisted': 'wishlist', # Spelling normalization
}

# Mapping of old stage values to canonical values (gerunds for ongoing processes)
STAGE_MAPPING = {
    'planned': 'planning',    # Gerund form for ongoing process
    'active': 'executing',    # Gerund form for ongoing process
    'approved': 'planning',   # Approved stories move to planning
}

# Canonical schema with updated CHECK constraints
CANONICAL_STORY_NODES_SCHEMA = """
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
    disposition TEXT DEFAULT NULL
        CHECK (disposition IS NULL OR disposition IN (
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
    success_criteria TEXT
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
        'hold_reason_values': {},
        'stage_values': {},
        'needs_migration': False,
        'schema_matches': True,
    }

    # Get current hold_reason distribution
    cursor.execute("""
        SELECT hold_reason, COUNT(*)
        FROM story_nodes
        WHERE hold_reason IS NOT NULL
        GROUP BY hold_reason
    """)
    for reason, count in cursor.fetchall():
        result['hold_reason_values'][reason] = count
        if reason in HOLD_REASON_MAPPING:
            result['needs_migration'] = True

    # Get current stage distribution
    cursor.execute("""
        SELECT stage, COUNT(*)
        FROM story_nodes
        GROUP BY stage
    """)
    for stage, count in cursor.fetchall():
        result['stage_values'][stage] = count
        if stage in STAGE_MAPPING:
            result['needs_migration'] = True

    # Check if schema already matches canonical
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='story_nodes'")
    schema = cursor.fetchone()[0]

    # Check for old values in CHECK constraint
    for old_val in HOLD_REASON_MAPPING.keys():
        if f"'{old_val}'" in schema:
            result['schema_matches'] = False

    for old_val in STAGE_MAPPING.keys():
        if f"'{old_val}'" in schema:
            result['schema_matches'] = False

    conn.close()
    return result


def migrate(db_path: Path, dry_run: bool = False) -> dict:
    """
    Migrate database to canonical v4.0 schema.

    Returns:
        dict with migration statistics
    """
    stats = {
        'data_migrations': {},
        'schema_updated': False,
        'backup_path': None,
        'version_updated': False,
    }

    analysis = analyze_current_schema(db_path)

    print(f"Database: {db_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    # Show current state
    print("Current stage distribution:")
    for stage, count in sorted(analysis['stage_values'].items()):
        needs_change = stage in STAGE_MAPPING
        marker = f" → {STAGE_MAPPING[stage]}" if needs_change else ""
        print(f"  {stage}: {count}{marker}")
    print()

    print("Current hold_reason distribution:")
    for reason, count in sorted(analysis['hold_reason_values'].items()):
        needs_change = reason in HOLD_REASON_MAPPING
        marker = f" → {HOLD_REASON_MAPPING[reason]}" if needs_change else ""
        print(f"  {reason}: {count}{marker}")
    print()

    if not analysis['needs_migration'] and analysis['schema_matches']:
        print("Database already matches canonical schema. No migration needed.")
        return stats

    if dry_run:
        print("[DRY RUN] Would perform the following migrations:")
        for old, new in STAGE_MAPPING.items():
            count = analysis['stage_values'].get(old, 0)
            if count > 0:
                print(f"  - Stage {old} → {new}: {count} rows")
        for old, new in HOLD_REASON_MAPPING.items():
            count = analysis['hold_reason_values'].get(old, 0)
            if count > 0:
                print(f"  - Hold {old} → {new}: {count} rows")
        print(f"  - Update CHECK constraints to canonical schema")
        return stats

    # Create backup
    backup_path = db_path.with_suffix(f'.db.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}')
    shutil.copy2(db_path, backup_path)
    stats['backup_path'] = str(backup_path)
    print(f"Created backup: {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Calculate expected migrations for reporting
    for old_val, new_val in STAGE_MAPPING.items():
        count = analysis['stage_values'].get(old_val, 0)
        if count > 0:
            stats['data_migrations'][f"stage: {old_val} → {new_val}"] = count

    for old_val, new_val in HOLD_REASON_MAPPING.items():
        count = analysis['hold_reason_values'].get(old_val, 0)
        if count > 0:
            stats['data_migrations'][f"hold: {old_val} → {new_val}"] = count

    # Step 1: Create new table with canonical schema and copy data with transformations
    print("\nStep 1: Creating new table with canonical schema...")
    cursor.execute("DROP TABLE IF EXISTS story_nodes_new")
    cursor.executescript(CANONICAL_STORY_NODES_SCHEMA)

    # Copy all data to new table, transforming stage and hold_reason values during copy
    print("\nStep 2: Migrating data with stage and hold_reason transformations...")
    cursor.execute("""
        INSERT INTO story_nodes_new (
            id, title, description, capacity, stage,
            hold_reason, disposition, human_review,
            project_path, last_implemented, notes,
            created_at, updated_at, version,
            story, success_criteria
        )
        SELECT
            id, title, description, capacity,
            CASE stage
                WHEN 'planned' THEN 'planning'
                WHEN 'active' THEN 'executing'
                WHEN 'approved' THEN 'planning'
                ELSE stage
            END as stage,
            CASE hold_reason
                WHEN 'escalated' THEN 'queued'
                WHEN 'conflicted' THEN 'conflict'
                WHEN 'wishlisted' THEN 'wishlist'
                ELSE hold_reason
            END as hold_reason,
            disposition, human_review,
            project_path, last_implemented, notes,
            created_at, updated_at, version,
            story, success_criteria
        FROM story_nodes
    """)

    # Step 3: Drop old table and rename new
    print("\nStep 3: Replacing old table with new...")
    cursor.execute("DROP TABLE story_nodes")
    cursor.execute("ALTER TABLE story_nodes_new RENAME TO story_nodes")
    stats['schema_updated'] = True
    print("  Schema updated to canonical v4.0")

    # Step 4: Recreate indexes
    print("\nStep 4: Recreating indexes...")
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_active_pipeline ON story_nodes(stage)
            WHERE disposition IS NULL AND hold_reason IS NULL;
        CREATE INDEX IF NOT EXISTS idx_held_stories ON story_nodes(hold_reason)
            WHERE hold_reason IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_disposed_stories ON story_nodes(disposition)
            WHERE disposition IS NOT NULL;
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
        VALUES ('schema_version', '4.0.0')
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('last_migration', ?)
    """, (datetime.now().isoformat(),))
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('migration_note', 'Migrated to canonical v4.0 three-field schema')
    """)
    stats['version_updated'] = True
    print("  Schema version updated to 4.0.0")

    conn.commit()
    conn.close()

    return stats


def verify(db_path: Path) -> bool:
    """Verify the migration was successful."""
    print(f"\nVerifying migration: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    success = True

    # Check schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='story_nodes'")
    schema = cursor.fetchone()[0]

    print("\nSchema CHECK constraints:")

    # Verify stage constraint
    if "'concept', 'planning', 'executing'" in schema:
        print("  [OK] stage matches canonical (gerund forms)")
    else:
        print("  [WARN] stage may not match canonical")
        success = False

    # Verify hold_reason constraint
    if "'queued', 'pending', 'paused', 'blocked', 'broken', 'polish', 'conflict', 'wishlist'" in schema:
        print("  [OK] hold_reason matches canonical")
    else:
        print("  [WARN] hold_reason may not match canonical")
        success = False

    # Check for old stage values in schema
    for old_val in STAGE_MAPPING.keys():
        if f"'{old_val}'" in schema:
            print(f"  [ERROR] Old stage value '{old_val}' still in schema")
            success = False

    # Check for old hold_reason values in schema
    for old_val in HOLD_REASON_MAPPING.keys():
        if f"'{old_val}'" in schema:
            print(f"  [ERROR] Old hold value '{old_val}' still in schema")
            success = False

    # Check for any data with old values
    print("\nData validation:")
    data_ok = True

    for old_val in STAGE_MAPPING.keys():
        cursor.execute("SELECT COUNT(*) FROM story_nodes WHERE stage = ?", (old_val,))
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"  [ERROR] {count} rows still have stage='{old_val}'")
            success = False
            data_ok = False

    for old_val in HOLD_REASON_MAPPING.keys():
        cursor.execute("SELECT COUNT(*) FROM story_nodes WHERE hold_reason = ?", (old_val,))
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"  [ERROR] {count} rows still have hold_reason='{old_val}'")
            success = False
            data_ok = False

    if data_ok:
        print("  [OK] No old values found in data")

    # Show current distribution
    print("\nCurrent stage distribution:")
    cursor.execute("""
        SELECT stage, COUNT(*)
        FROM story_nodes
        GROUP BY stage
        ORDER BY stage
    """)
    for stage, count in cursor.fetchall():
        print(f"  {stage}: {count}")

    print("\nCurrent hold_reason distribution:")
    cursor.execute("""
        SELECT hold_reason, COUNT(*)
        FROM story_nodes
        WHERE hold_reason IS NOT NULL
        GROUP BY hold_reason
        ORDER BY hold_reason
    """)
    for reason, count in cursor.fetchall():
        print(f"  {reason}: {count}")

    # Check metadata
    print("\nMetadata:")
    cursor.execute("SELECT key, value FROM metadata WHERE key IN ('schema_version', 'last_migration')")
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
        description='Migrate SyncoPaid story-tree.db to canonical v4.0 schema'
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

    if not args.dry_run and (stats['schema_updated'] or stats['data_migrations']):
        print("\n" + "=" * 50)
        print("Migration Summary")
        print("=" * 50)
        if stats['data_migrations']:
            print("Data migrations:")
            for migration, count in stats['data_migrations'].items():
                print(f"  {migration}: {count} rows")
        if stats['schema_updated']:
            print("Schema: Updated to canonical v4.0")
        if stats['backup_path']:
            print(f"Backup: {stats['backup_path']}")
        print()

        verify(db_path)

    return 0


if __name__ == '__main__':
    exit(main())
