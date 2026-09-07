#!/usr/bin/env python3
"""Codex hook: re-inject the Astra behavior rules that Sol / Terra tend to forget.

Reads the hook payload (JSON) from stdin and prints developer context to stdout.

- SessionStart: prints the compact rule card so every session starts with the rules
  in context even when developer_instructions is not attached (e.g. Codex App).
- PostCompact: prints the compaction rule plus the running notes file, if present,
  so the original objective survives context compaction.
"""
from __future__ import annotations

import json
import os
import sys

RULE_CARD = """\
Astra behavior rules (astra-riding overlay, condensed):
1. Requests phrased as "can you" / "I want" / "help me" are instructions: do the work, do not stop at a plan or a yes.
2. Persist until the intended goal is complete. Do not trim scope to save effort; if something is blocked, finish the rest and say what is left.
3. Ask only questions whose answer changes the outcome. Decide inferable details yourself and list the assumptions at the end.
4. Keep working on everything that does not depend on a pending answer. Only irreversible or external actions wait for approval; elapsed time is not approval.
5. Approval, when required, is the final step: do all authorized work first so the user approves a concrete result.
6. User instructions outrank skills, AGENTS.md, and memory. If a file makes you pause, cite the file and the line.
7. A new message during work is steering, not a replacement. Keep the original objective.
8. Every claim about changes or tests must be backed by output you saw in this session. Say first what you could not verify.
9. Verify in proportion to the change; once checks pass, do not widen them without a reason.
10. Final answer: outcome first, then what changed, why, how it was tested, remaining risk. No filler, no "X rather than Y" framing.
"""

COMPACT_RULE = """\
Context was compacted. The task has NOT ended. Preserve the original objective, accepted corrections, constraints, completed work, and outstanding work. Treat the latest user message as steering, not as a new objective. Do not restart or redo finished work.
"""

NOTES_ENV = "ASTRA_NOTES_FILE"
DEFAULT_NOTES = os.path.join(".codex", "astra-notes.md")


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def notes_text() -> str:
    path = os.environ.get(NOTES_ENV, DEFAULT_NOTES)
    try:
        with open(path, encoding="utf-8") as fh:
            body = fh.read().strip()
    except OSError:
        return ""
    if not body:
        return ""
    return f"\nRunning notes from {path}:\n{body}\n"


def main() -> int:
    payload = read_payload()
    event = payload.get("hook_event_name", "")
    if event == "PostCompact":
        out = COMPACT_RULE + notes_text() + "\n" + RULE_CARD
    else:
        out = RULE_CARD + notes_text()
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
