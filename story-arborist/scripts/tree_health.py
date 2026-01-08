#!/usr/bin/env python
"""Generate comprehensive tree health report.

Usage: python tree_health.py [--json]
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'story-tree', 'utility'))
from story_db_common import get_connection, validate_tree_structure

def main():
    output_json = '--json' in sys.argv

    conn = get_connection()

    # Structural issues
    issues = validate_tree_structure(conn)

    # Basic statistics
    stats = {}

    stats['total_nodes'] = conn.execute(
        "SELECT COUNT(*) FROM story_nodes WHERE story_path != 'root'"
    ).fetchone()[0]

    stats['max_depth'] = conn.execute(
        "SELECT MAX(depth) FROM story_paths WHERE ancestor_id = 'root'"
    ).fetchone()[0] or 0

    # Stage distribution
    stats['by_stage'] = {}
    for row in conn.execute('''
        SELECT stage, COUNT(*) FROM story_nodes
        WHERE story_path != 'root' AND terminus IS NULL AND status = 'ready'
        GROUP BY stage ORDER BY stage
    ''').fetchall():
        stats['by_stage'][row[0]] = row[1]

    # Status distribution (non-ready)
    stats['by_status'] = {}
    for row in conn.execute('''
        SELECT status, COUNT(*) FROM story_nodes
        WHERE status != 'ready'
        GROUP BY status ORDER BY status
    ''').fetchall():
        stats['by_status'][row[0]] = row[1]

    # Terminus distribution
    stats['by_terminus'] = {}
    for row in conn.execute('''
        SELECT terminus, COUNT(*) FROM story_nodes
        WHERE terminus IS NOT NULL
        GROUP BY terminus ORDER BY terminus
    ''').fetchall():
        stats['by_terminus'][row[0]] = row[1]

    # Nodes needing review
    stats['needs_review'] = conn.execute(
        "SELECT COUNT(*) FROM story_nodes WHERE human_review = 1"
    ).fetchone()[0]

    # Top-level epics
    stats['root_children'] = conn.execute('''
        SELECT COUNT(*) FROM story_paths
        WHERE ancestor_id = 'root' AND depth = 1
    ''').fetchone()[0]

    conn.close()

    # Count total issues
    total_issues = sum(len(v) for v in issues.values())

    if output_json:
        report = {
            'generated_at': datetime.now().isoformat(),
            'statistics': stats,
            'issues': issues,
            'total_issues': total_issues,
            'health_status': 'healthy' if total_issues == 0 else 'issues_found'
        }
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print("STORY TREE HEALTH REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        print("\n--- STATISTICS ---")
        print(f"Total nodes: {stats['total_nodes']}")
        print(f"Max depth: {stats['max_depth']}")
        print(f"Root-level epics: {stats['root_children']}")
        print(f"Needs human review: {stats['needs_review']}")

        if stats['by_stage']:
            print("\nActive pipeline (by stage):")
            for stage, count in stats['by_stage'].items():
                print(f"  {stage}: {count}")

        if stats['by_status']:
            print("\nNon-ready (by status):")
            for status, count in stats['by_status'].items():
                print(f"  {status}: {count}")

        if stats['by_terminus']:
            print("\nExited pipeline (by terminus):")
            for term, count in stats['by_terminus'].items():
                print(f"  {term}: {count}")

        print("\n--- STRUCTURAL HEALTH ---")
        if total_issues == 0:
            print("No structural issues found.")
        else:
            print(f"Found {total_issues} issue(s):")
            for category, items in issues.items():
                if items:
                    print(f"\n  {category.upper().replace('_', ' ')}:")
                    for item in items[:5]:
                        if 'reason' in item:
                            print(f"    - {item['id']}: {item['reason']}")
                        elif 'actual_parent' in item:
                            print(f"    - {item['id']}: expected parent {item['expected_parent']}, found {item['actual_parent']}")
                        else:
                            print(f"    - {item['id']}: {item.get('title', 'N/A')}")
                    if len(items) > 5:
                        print(f"    ... and {len(items) - 5} more")

        print("\n" + "=" * 60)
        status = "HEALTHY" if total_issues == 0 else f"ISSUES FOUND ({total_issues})"
        print(f"Status: {status}")
        print("=" * 60)

    return 0 if total_issues == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
