#!/usr/bin/env python3
"""
Migration: v4.1 Planning Stage Redesign

Updates:
1. Renames stage values: approved→planning, planned→planning, active→executing
2. Adds new columns: user_journeys, dependencies, prerequisites
3. Removes obsolete stage value 'polish' (now a hold_reason only)

Usage: python -m distributables.scripts.migrations.migrate_v4.1_planning_redesign
   Or: python distributables/scripts/migrations/migrate_v4.1_planning_redesign.py
"""
import sqlite3
import os
import sys
from datetime import datetime
from pathlib import Path

# Add scripts directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_db_path

# Database path
DB_PATH = str(get_db_path())

# Stage value mappings (old → new)
STAGE_MAPPINGS = {
    'approved': 'planning',
    'planned': 'planning',
    'active': 'executing',
    'polish': 'ready',  # Polish stage → ready (polish is now a hold_reason)
}


def check_column_exists(cursor, table, column):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_stages(cursor):
    """Migrate old stage values to new ones."""
    changes = []
    for old_stage, new_stage in STAGE_MAPPINGS.items():
        cursor.execute(
            "SELECT COUNT(*) FROM story_nodes WHERE stage = ?",
            (old_stage,)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            cursor.execute(
                "UPDATE story_nodes SET stage = ? WHERE stage = ?",
                (new_stage, old_stage)
            )
            changes.append((old_stage, new_stage, count))
    return changes


def add_planning_columns(cursor):
    """Add new planning stage columns if they don't exist."""
    columns_added = []
    new_columns = [
        ('user_journeys', 'TEXT'),
        ('dependencies', 'TEXT'),
        ('prerequisites', 'TEXT'),
        ('debug_attempts', 'INTEGER DEFAULT 0'),
    ]
    for col_name, col_type in new_columns:
        if not check_column_exists(cursor, 'story_nodes', col_name):
            cursor.execute(f"ALTER TABLE story_nodes ADD COLUMN {col_name} {col_type}")
            columns_added.append(col_name)
    return columns_added


def main():
    if not os.path.exists(DB_PATH):
        print(f'[ERROR] Database not found: {DB_PATH}')
        print('Run this migration from the project root directory.')
        return 1

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print('=' * 70)
    print('Migration: v4.1 Planning Stage Redesign')
    print(f'Database: {DB_PATH}')
    print(f'Timestamp: {datetime.now().isoformat()}')
    print('=' * 70)
    print()

    # Step 1: Add new columns
    print('[1/2] Adding new planning columns...')
    columns_added = add_planning_columns(cursor)
    if columns_added:
        for col in columns_added:
            print(f'  [ADDED] {col}')
    else:
        print('  [OK] All columns already exist')
    print()

    # Step 2: Migrate stage values
    print('[2/2] Migrating stage values...')
    stage_changes = migrate_stages(cursor)
    if stage_changes:
        for old_stage, new_stage, count in stage_changes:
            print(f'  [MIGRATED] {old_stage} → {new_stage} ({count} stories)')
    else:
        print('  [OK] No stage values need migration')
    print()

    # Commit changes
    conn.commit()

    # Summary
    print('=' * 70)
    print('MIGRATION COMPLETE')
    print('=' * 70)
    if columns_added or stage_changes:
        print()
        print('Changes made:')
        for col in columns_added:
            print(f'  + Added column: {col}')
        for old_stage, new_stage, count in stage_changes:
            print(f'  ~ Renamed stage: {old_stage} → {new_stage} ({count} rows)')
    else:
        print('No changes needed - database already up to date.')
    print()

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
