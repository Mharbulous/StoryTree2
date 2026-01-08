#!/usr/bin/env python3
"""
Migrate story-tree.db to add 'epic' stage for container-only nodes.

This script:
1. Adds 'epic' to the stage CHECK constraint
2. Converts root node to epic stage
3. Converts all level-1 nodes (direct children of root) to epic stage
4. Clears hold_reason for converted nodes (epics don't participate in workflow)

Usage:
    python migrate_to_epic_stage.py              # Run migration
    python migrate_to_epic_stage.py --dry-run    # Preview only
    python migrate_to_epic_stage.py --verify     # Check results
    python migrate_to_epic_stage.py --rollback   # Restore from backup
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent.parent.parent / '.claude' / 'data' / 'story-tree.db'

# New schema with 'epic' added to stage CHECK constraint
NEW_STORY_NODES_SCHEMA = """
CREATE TABLE story_nodes_new (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    capacity INTEGER,
    stage TEXT NOT NULL DEFAULT 'concept'
        CHECK (stage IN (
            'epic',
            'concept', 'planning', 'implementing', 'testing', 'releasing', 'shipped',
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


def is_level1_id(node_id: str) -> bool:
    """Check if a node ID is a level-1 node (direct child of root)."""
    # Level-1 IDs are plain integers without dots (e.g., '1', '2', '15')
    # Root is 'root', level-2+ have dots (e.g., '1.1', '8.4.2')
    if node_id == 'root':
        return False
    return '.' not in node_id and node_id.isdigit()


def analyze_current_data(db_path: Path) -> dict:
    """Analyze current database to determine what needs migration."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result = {
        'total_rows': 0,
        'root_stage': None,
        'level1_nodes': [],
        'epic_exists': False,
        'stage_counts': {},
    }

    # Get total row count
    cursor.execute("SELECT COUNT(*) FROM story_nodes")
    result['total_rows'] = cursor.fetchone()[0]

    # Check root node
    cursor.execute("SELECT stage, hold_reason FROM story_nodes WHERE id = 'root'")
    row = cursor.fetchone()
    if row:
        result['root_stage'] = row[0]

    # Find level-1 nodes (direct children of root)
    cursor.execute("""
        SELECT s.id, s.title, s.stage, s.hold_reason
        FROM story_nodes s
        WHERE s.id != 'root' AND s.id NOT LIKE '%.%'
        ORDER BY CAST(s.id AS INTEGER)
    """)
    for row in cursor.fetchall():
        if is_level1_id(row[0]):
            result['level1_nodes'].append({
                'id': row[0],
                'title': row[1],
                'stage': row[2],
                'hold_reason': row[3],
            })

    # Check if any nodes already have 'epic' stage
    cursor.execute("SELECT COUNT(*) FROM story_nodes WHERE stage = 'epic'")
    result['epic_exists'] = cursor.fetchone()[0] > 0

    # Get stage distribution
    cursor.execute("SELECT stage, COUNT(*) FROM story_nodes GROUP BY stage ORDER BY stage")
    for stage, count in cursor.fetchall():
        result['stage_counts'][stage or 'NULL'] = count

    conn.close()
    return result


def migrate(db_path: Path, dry_run: bool = False) -> dict:
    """
    Migrate database: add 'epic' stage and convert root + level-1 nodes.

    Uses CREATE-COPY-RENAME pattern to update schema and values.

    Returns:
        dict with migration statistics
    """
    stats = {
        'nodes_converted': 0,
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
    print(f"  Root stage: {analysis['root_stage']}")
    print(f"  Level-1 nodes: {len(analysis['level1_nodes'])}")
    print()

    if analysis['epic_exists']:
        print("[WARNING] Some nodes already have 'epic' stage. Proceeding anyway.")
        print()

    print("Nodes to convert to epic:")
    print(f"  root: {analysis['root_stage']} -> epic")
    for node in analysis['level1_nodes']:
        hold = f" ({node['hold_reason']})" if node['hold_reason'] else ""
        print(f"  {node['id']}: {node['stage']}{hold} -> epic (title: {node['title'][:40]}...)")
    print()

    nodes_to_convert = 1 + len(analysis['level1_nodes'])  # root + level-1 nodes

    if dry_run:
        print(f"[DRY RUN] Would convert {nodes_to_convert} nodes to 'epic' stage")
        print("[DRY RUN] Would update schema to add 'epic' to CHECK constraint")
        return stats

    # Create backup
    backup_path = db_path.with_suffix(f'.db.backup-epic-{datetime.now().strftime("%Y%m%d-%H%M%S")}')
    shutil.copy2(db_path, backup_path)
    stats['backup_path'] = str(backup_path)
    print(f"Created backup: {backup_path}\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Step 1: Create new table with updated schema
    print("Step 1: Creating new table with 'epic' in CHECK constraint...")
    cursor.execute("DROP TABLE IF EXISTS story_nodes_new")
    cursor.executescript(NEW_STORY_NODES_SCHEMA)

    # Step 2: Copy all data with epic conversion for root and level-1 nodes
    print("\nStep 2: Migrating data with epic conversion...")

    # Build the CASE expression for level-1 IDs
    level1_ids = [node['id'] for node in analysis['level1_nodes']]
    level1_ids_sql = ', '.join(f"'{id}'" for id in level1_ids)

    # SQL to convert root and level-1 nodes to epic, clear their hold_reason
    cursor.execute(f"""
        INSERT INTO story_nodes_new (
            id, title, description, capacity, stage,
            hold_reason, terminus, human_review,
            user_journeys, dependencies, prerequisites, debug_attempts,
            project_path, last_implemented, notes,
            created_at, updated_at, version,
            story, success_criteria
        )
        SELECT
            id, title, description, capacity,
            CASE
                WHEN id = 'root' THEN 'epic'
                WHEN id IN ({level1_ids_sql}) THEN 'epic'
                ELSE stage
            END as stage,
            CASE
                WHEN id = 'root' THEN NULL
                WHEN id IN ({level1_ids_sql}) THEN NULL
                ELSE hold_reason
            END as hold_reason,
            terminus, human_review,
            user_journeys, dependencies, prerequisites, debug_attempts,
            project_path, last_implemented, notes,
            created_at, updated_at, version,
            story, success_criteria
        FROM story_nodes
    """)
    stats['total_rows_migrated'] = cursor.rowcount
    stats['nodes_converted'] = nodes_to_convert
    print(f"  Migrated {stats['total_rows_migrated']} rows")
    print(f"  Converted {stats['nodes_converted']} nodes to epic")

    # Step 3: Drop old table and rename new
    print("\nStep 3: Replacing old table with new...")
    cursor.execute("DROP TABLE story_nodes")
    cursor.execute("ALTER TABLE story_nodes_new RENAME TO story_nodes")
    stats['schema_updated'] = True
    print("  Schema updated with 'epic' in CHECK constraint")

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
        VALUES ('schema_version', '4.3.0')
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('last_migration', ?)
    """, (datetime.now().isoformat(),))
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('migration_note', 'Added epic stage; converted root and level-1 nodes to epic')
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

    # Check root is epic
    print("\nRoot node verification:")
    cursor.execute("SELECT stage, hold_reason FROM story_nodes WHERE id = 'root'")
    row = cursor.fetchone()
    if row:
        if row[0] == 'epic':
            print(f"  [OK] Root is epic (hold_reason: {row[1]})")
        else:
            print(f"  [ERROR] Root is '{row[0]}', expected 'epic'")
            success = False
    else:
        print("  [ERROR] Root node not found")
        success = False

    # Check level-1 nodes are epic
    print("\nLevel-1 node verification:")
    cursor.execute("""
        SELECT id, stage, hold_reason
        FROM story_nodes
        WHERE id != 'root' AND id NOT LIKE '%.%'
        ORDER BY CAST(id AS INTEGER)
    """)
    for row in cursor.fetchall():
        if is_level1_id(row[0]):
            if row[1] == 'epic':
                print(f"  [OK] Node {row[0]} is epic")
            else:
                print(f"  [ERROR] Node {row[0]} is '{row[1]}', expected 'epic'")
                success = False

    # Show stage distribution
    print("\nCurrent STAGE distribution:")
    cursor.execute("SELECT stage, COUNT(*) FROM story_nodes GROUP BY stage ORDER BY stage")
    for stage, count in cursor.fetchall():
        print(f"  {stage or 'NULL'}: {count}")

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


def rollback(db_path: Path) -> bool:
    """Rollback to the most recent backup."""
    # Find the most recent epic backup
    backup_pattern = db_path.with_suffix('.db.backup-epic-*')
    backups = sorted(db_path.parent.glob('story-tree.db.backup-epic-*'), reverse=True)

    if not backups:
        print("No epic migration backups found")
        return False

    latest_backup = backups[0]
    print(f"Found backup: {latest_backup}")
    print(f"Restoring to: {db_path}")

    shutil.copy2(latest_backup, db_path)
    print("Rollback complete")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Migrate story-tree.db to add 'epic' stage"
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
    parser.add_argument(
        '--rollback', action='store_true',
        help='Rollback to the most recent backup'
    )

    args = parser.parse_args()

    try:
        db_path = args.db or find_db()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    if args.rollback:
        return 0 if rollback(db_path) else 1

    if args.verify:
        return 0 if verify(db_path) else 1

    stats = migrate(db_path, dry_run=args.dry_run)

    if not args.dry_run and stats['schema_updated']:
        print("\n" + "=" * 50)
        print("Migration Summary")
        print("=" * 50)
        print(f"Total rows migrated: {stats['total_rows_migrated']}")
        print(f"Nodes converted to epic: {stats['nodes_converted']}")
        print(f"Schema updated: Yes ('epic' added to CHECK constraint)")
        if stats['backup_path']:
            print(f"Backup: {stats['backup_path']}")
        print()

        verify(db_path)

    return 0


if __name__ == '__main__':
    exit(main())
