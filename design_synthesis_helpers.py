#!/usr/bin/env python3
"""Helper script for design synthesis from story-tree database.

Extracts UI/UX patterns and anti-patterns from story data.
"""
import sqlite3
import os
import json
from datetime import date

from config import get_db_path, get_data_dir

DB_PATH = str(get_db_path())
DESIGN_DIR = str(get_data_dir() / 'design')
META_FILE = f'{DESIGN_DIR}/synthesis-meta.json'

# Keywords that indicate UI/UX related content
UI_UX_KEYWORDS = [
    'ui', 'ux', 'design', 'layout', 'component', 'button', 'form',
    'modal', 'dialog', 'menu', 'navigation', 'nav', 'style', 'theme',
    'color', 'font', 'icon', 'responsive', 'accessibility', 'a11y',
    'widget', 'panel', 'tab', 'dropdown', 'input', 'checkbox', 'radio',
    'tooltip', 'popup', 'sidebar', 'header', 'footer', 'grid', 'flex',
    'animation', 'transition', 'hover', 'focus', 'click', 'scroll',
    'drag', 'drop', 'resize', 'visual', 'display', 'view', 'screen',
    'window', 'pane', 'toolbar', 'statusbar', 'treeview', 'listview',
    'table', 'card', 'banner', 'alert', 'notification', 'toast',
    'spinner', 'loader', 'progress', 'slider', 'toggle', 'switch'
]


def build_keyword_condition():
    """Build SQL condition for matching UI/UX keywords."""
    conditions = []
    for kw in UI_UX_KEYWORDS:
        conditions.append(f"LOWER(title) LIKE '%{kw}%'")
        conditions.append(f"LOWER(description) LIKE '%{kw}%'")
        conditions.append(f"LOWER(notes) LIKE '%{kw}%'")
    return ' OR '.join(conditions)


def get_prerequisites():
    """Return all prerequisite data in one call.

    Compares current DB counts against synthesis-meta.json to determine
    if re-synthesis is needed.
    """
    result = {
        'db_exists': os.path.exists(DB_PATH),
        'ui_implemented_count': 0,
        'ui_rejected_count': 0,
        'needs_patterns_update': True,
        'needs_anti_patterns_update': True,
        'last_synthesis': None,
    }

    if result['db_exists']:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        keyword_cond = build_keyword_condition()

        # Count implemented stories with UI/UX keywords
        # Stages: implemented, ready, released are considered "implemented"
        cursor.execute(f'''
            SELECT COUNT(*) FROM story_nodes
            WHERE stage IN ('implemented', 'ready', 'released')
            AND status = 'ready'
            AND terminus IS NULL
            AND ({keyword_cond})
        ''')
        result['ui_implemented_count'] = cursor.fetchone()[0]

        # Count rejected stories with UI/UX keywords
        cursor.execute(f'''
            SELECT COUNT(*) FROM story_nodes
            WHERE terminus = 'rejected'
            AND notes IS NOT NULL AND notes != ''
            AND ({keyword_cond})
        ''')
        result['ui_rejected_count'] = cursor.fetchone()[0]
        conn.close()

    # Compare against last synthesis metadata
    if os.path.exists(META_FILE):
        with open(META_FILE) as f:
            meta = json.load(f)
        result['last_synthesis'] = meta.get('last_synthesis')
        result['needs_patterns_update'] = result['ui_implemented_count'] != meta.get('ui_implemented_count', 0)
        result['needs_anti_patterns_update'] = result['ui_rejected_count'] != meta.get('ui_rejected_count', 0)

    print(json.dumps(result, indent=2))
    return result


def update_synthesis_meta():
    """Update synthesis-meta.json after successful synthesis."""
    today = date.today().strftime('%Y-%m-%d')

    ui_implemented_count = 0
    ui_rejected_count = 0

    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        keyword_cond = build_keyword_condition()

        cursor.execute(f'''
            SELECT COUNT(*) FROM story_nodes
            WHERE stage IN ('implemented', 'ready', 'released')
            AND status = 'ready'
            AND terminus IS NULL
            AND ({keyword_cond})
        ''')
        ui_implemented_count = cursor.fetchone()[0]

        cursor.execute(f'''
            SELECT COUNT(*) FROM story_nodes
            WHERE terminus = 'rejected'
            AND notes IS NOT NULL AND notes != ''
            AND ({keyword_cond})
        ''')
        ui_rejected_count = cursor.fetchone()[0]
        conn.close()

    meta = {
        'last_synthesis': today,
        'ui_implemented_count': ui_implemented_count,
        'ui_rejected_count': ui_rejected_count
    }

    os.makedirs(DESIGN_DIR, exist_ok=True)
    with open(META_FILE, 'w') as f:
        json.dump(meta, f, indent=2)
        f.write('\n')

    print(json.dumps({'status': 'updated', **meta}, indent=2))


def get_pattern_stories():
    """Output implemented UI/UX stories for pattern synthesis."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    keyword_cond = build_keyword_condition()

    cursor.execute(f'''
        SELECT id, title, description, notes FROM story_nodes
        WHERE stage IN ('implemented', 'ready', 'released')
        AND status = 'ready'
        AND terminus IS NULL
        AND ({keyword_cond})
        ORDER BY id
    ''')
    for row in cursor.fetchall():
        print(f'=== {row[0]}: {row[1]} ===')
        print(row[2])
        if row[3]:
            print(f'Implementation Notes: {row[3]}')
        print()
    conn.close()


def get_anti_pattern_stories():
    """Output rejected UI/UX stories for anti-pattern synthesis."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    keyword_cond = build_keyword_condition()

    cursor.execute(f'''
        SELECT id, title, description, notes FROM story_nodes
        WHERE terminus = 'rejected'
        AND notes IS NOT NULL AND notes != ''
        AND ({keyword_cond})
        ORDER BY id
    ''')
    for row in cursor.fetchall():
        print(f'=== {row[0]}: {row[1]} ===')
        print(row[2])
        print(f'REJECTION REASON: {row[3]}')
        print()
    conn.close()


if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'prereq'
    commands = {
        'prereq': get_prerequisites,
        'patterns': get_pattern_stories,
        'anti-patterns': get_anti_pattern_stories,
        'update-meta': update_synthesis_meta
    }
    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(commands.keys())}")
        sys.exit(1)
