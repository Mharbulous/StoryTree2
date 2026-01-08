#!/usr/bin/env python3
"""
Cross-Agent Notification Hook (v2 - NDJSON optimized)

Checks for unread messages using efficient partial reads.
Always exits with code 0 to avoid blocking prompts.
"""

import json
import sys
from pathlib import Path

# Configuration
CROSS_AGENT_DIR = Path(r"C:\Users\Brahm\Git\.cross-agent")
THREADS_DIR = CROSS_AGENT_DIR / "threads"
STATE_FILE = Path(__file__).parent / ".cross_agent_state.json"

def get_agent_name() -> str:
    """Derive agent name from repository directory name."""
    try:
        repo_root = Path(__file__).parent.parent.parent
        return repo_root.name
    except Exception:
        return "Unknown"

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {"notified_messages": {}}

def save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')
    except Exception:
        pass  # Fail silently

def check_thread_optimized(thread_file: Path, agent_name: str, notified: dict) -> list:
    """Check a single thread file, reading only first few lines."""
    unread = []

    try:
        with open(thread_file, 'r', encoding='utf-8') as f:
            # Line 1: Header
            header_line = f.readline().strip()
            if not header_line:
                return unread
            header = json.loads(header_line)

            # Check if we're a participant
            participants = header.get("participants", [])
            if agent_name not in participants:
                return unread

            thread_id = header.get("thread_id", thread_file.stem)

            # Read up to 5 recent messages to catch any unread
            for _ in range(5):
                msg_line = f.readline().strip()
                if not msg_line:
                    break

                msg = json.loads(msg_line)
                msg_id = str(msg.get("id", ""))
                msg_key = f"{thread_id}:{msg_id}"

                # Skip if already notified
                if msg_key in notified:
                    continue

                to_agent = msg.get("to", "")
                status = msg.get("status", "")
                from_agent = msg.get("from", "unknown")

                # Check if message is for us and unread
                if status == "unread" and (to_agent == agent_name or to_agent == "all"):
                    if from_agent != agent_name:
                        unread.append((from_agent, str(thread_file), msg_key))

    except Exception:
        pass  # Fail silently

    return unread

def main():
    try:
        agent_name = get_agent_name()
        state = load_state()
        notified = state.get("notified_messages", {})

        all_unread = []

        if THREADS_DIR.exists():
            # v2: Look for .ndjson files
            for thread_file in THREADS_DIR.glob("*.ndjson"):
                all_unread.extend(check_thread_optimized(thread_file, agent_name, notified))

        if not all_unread:
            sys.exit(0)

        notifications = []
        for from_agent, thread_file, msg_key in all_unread:
            notifications.append(
                f"Incoming message received from: {from_agent}\n"
                f"Please view the message here: {thread_file}"
            )
            state.setdefault("notified_messages", {})[msg_key] = True

        save_state(state)
        print("\n---\n".join(notifications))

    except Exception:
        pass  # Fail silently, never block

    sys.exit(0)  # Always exit 0 to avoid blocking

if __name__ == "__main__":
    main()
