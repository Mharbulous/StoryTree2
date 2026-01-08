#!/usr/bin/env python
"""List orphaned nodes (exist in story_nodes but not in story_paths).

Usage: python list_orphans.py [--ids-only]
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'story-tree', 'utility'))
from story_db_common import get_connection

def main():
    ids_only = '--ids-only' in sys.argv

    conn = get_connection()
    orphans = conn.execute('''
        SELECT sn.story_path, sn.title, sn.stage, sn.status, sn.terminus
        FROM story_nodes sn
        WHERE sn.story_path != 'root'
          AND NOT EXISTS (
              SELECT 1 FROM story_paths sp WHERE sp.descendant_id = sn.story_path
          )
        ORDER BY sn.story_path
    ''').fetchall()
    conn.close()

    if not orphans:
        if not ids_only:
            print("No orphaned nodes found.")
        return 0

    if ids_only:
        for (node_id, _, _, _, _) in orphans:
            print(node_id)
    else:
        print(f"Found {len(orphans)} orphaned node(s):\n")
        for (node_id, title, stage, status, terminus) in orphans:
            display_status = terminus or (status if status != 'ready' else None) or stage
            print(f"  {node_id}: [{display_status}] {title}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
