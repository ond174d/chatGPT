#!/usr/bin/env python3
"""Agent hook: inject the astra-riding rule card, and restore the objective after compaction.

Harness-neutral. Reads a JSON hook payload on stdin (missing or unparsable payload is fine)
and writes context to stdout. Works with any agent whose hooks add stdout to the model's
context: Claude Code (SessionStart with source startup/resume/clear/compact, PreCompact),
Codex (SessionStart, PostCompact), and anything with a comparable event.

The event is read from `hook_event_name`; the SessionStart trigger from `source`.
Any event whose name or source mentions compaction also gets the continuity reminder.

Environment:
  ASTRA_RULECARD  path to the rule card (default: rulecard.md next to this script)
  ASTRA_NOTES     path to the running notes file (default: .astra-notes.md in the cwd)
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CARD = os.path.join(HERE, "rulecard.md")
DEFAULT_NOTES = ".astra-notes.md"

CONTINUITY = (
    "Context was compacted. The task has NOT ended. Preserve the original objective, "
    "accepted corrections, constraints, completed work, and outstanding work. Treat the "
    "latest message as steering, not as a new objective. Do not restart or redo finished work."
)

FALLBACK_CARD = (
    "Operating rules (astra-riding): treat requests as instructions and finish them; ask only "
    "questions that change the outcome and keep working meanwhile; require approval only for "
    "irreversible or outward-facing actions, and ask last; back every claim with something you "
    "observed; verify in proportion to impact; report outcome first in the person's language."
)


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
    except (OSError, UnicodeDecodeError):
        return {}
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def is_compaction(payload: dict) -> bool:
    marker = "compact"
    event = str(payload.get("hook_event_name", "")).lower()
    source = str(payload.get("source", "")).lower()
    return marker in event or marker in source


def main() -> int:
    payload = read_payload()
    card = read_file(os.environ.get("ASTRA_RULECARD", DEFAULT_CARD)) or FALLBACK_CARD
    notes = read_file(os.environ.get("ASTRA_NOTES", DEFAULT_NOTES))

    parts = []
    if is_compaction(payload):
        parts.append(CONTINUITY)
    if notes:
        parts.append("Running notes:\n" + notes)
    parts.append(card)
    sys.stdout.write("\n\n".join(parts) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
