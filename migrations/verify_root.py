#!/usr/bin/env python3
"""Verify story tree root node."""
import sqlite3
import sys
from pathlib import Path

# Add scripts directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_db_path

conn = sqlite3.connect(str(get_db_path()))
cursor = conn.cursor()

# Query root node
cursor.execute("SELECT id, title, description, capacity, status FROM story_nodes WHERE id='root'")
row = cursor.fetchone()

if row:
    print(f"Root Node Found:")
    print(f"  ID: {row[0]}")
    print(f"  Title: {row[1]}")
    print(f"  Description: {row[2]}")
    print(f"  Capacity: {row[3]}")
    print(f"  Status: {row[4]}")
else:
    print("ERROR: No root node found!")

# Query closure table
cursor.execute("SELECT ancestor_id, descendant_id, depth FROM story_paths WHERE ancestor_id='root'")
paths = cursor.fetchall()
print(f"\nClosure table entries: {len(paths)}")
for path in paths:
    print(f"  {path[0]} -> {path[1]} (depth {path[2]})")

conn.close()
