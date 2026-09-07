#!/usr/bin/env python3
"""エージェントの指示ファイルから、astra-riding の自律動作と衝突しやすい記述を洗い出す。

対象は AGENTS.md / CLAUDE.md / GEMINI.md / SKILL.md / .cursorrules / .cursor/rules/*.mdc /
.github/copilot-instructions.md など、主要なエージェントが読む指示ファイル。

使い方:
    python3 audit_instructions.py [ROOT ...]

ROOT 以下(既定はカレントディレクトリ)を再帰的に走査し、承認を強制する表現や
絶対禁止の表現を含む行を `path:line: 種別: 行` の形式で出力する。
何も見つからなければ終了コード 0、見つかれば 1 を返す。
"""
from __future__ import annotations

import os
import re
import sys

TARGET_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "SKILL.md",
    "copilot-instructions.md",
    ".cursorrules",
    ".windsurfrules",
    ".clinerules",
}
TARGET_SUFFIXES = (".mdc",)  # .cursor/rules/*.mdc
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".next", "target", "vendor"}

# 種別 -> 正規表現(日本語・英語)。大文字小文字は区別しない。
PATTERNS: dict[str, re.Pattern[str]] = {
    "approval-forcing": re.compile(
        r"(常に|必ず|毎回|事前に)[^\n]{0,20}(確認|承認|許可|質問|聞い|尋ね)"
        r"|(確認|承認|許可)[^\n]{0,10}(してから|を得てから|なしに[^\n]{0,6}ない)"
        r"|\b(always|first|before[^\n]{0,20})\s+(ask|confirm|check with|get (approval|permission))"
        r"|\bask\s+(for\s+)?(permission|confirmation|approval)\b"
        r"|\bdo not proceed without\b|\bnever proceed without\b|\bwait for (my|user) (approval|confirmation)\b",
        re.IGNORECASE,
    ),
    "absolute-prohibition": re.compile(
        r"(絶対に|決して|いかなる場合も)[^\n]{0,20}(ない|禁止|しないこと)"
        r"|\b(never|under no circumstances|must not|do not ever)\b",
        re.IGNORECASE,
    ),
    "stop-and-report": re.compile(
        r"(作業を止め|中断し|停止し)[^\n]{0,15}(報告|確認)"
        r"|\bstop (and|to) (ask|report|confirm)\b|\bpause (and|to) (ask|confirm)\b",
        re.IGNORECASE,
    ),
}


def iter_targets(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name in TARGET_NAMES or _matches(name):
                yield os.path.join(dirpath, name)


def _matches(name: str) -> bool:
    lowered = name.lower()
    if lowered in {n.lower() for n in TARGET_NAMES}:
        return True
    return name.endswith(TARGET_SUFFIXES)


MANAGED_BEGIN = "astra-riding:overlay:start"
MANAGED_END = "astra-riding:overlay:end"


def audit_file(path: str) -> list[tuple[int, str, str]]:
    """管理ブロック(install.py が埋め込むオーバーレイ)は監査対象から外す。"""
    hits: list[tuple[int, str, str]] = []
    in_managed = False
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                stripped = line.rstrip("\n")
                if MANAGED_BEGIN in stripped:
                    in_managed = True
                    continue
                if MANAGED_END in stripped:
                    in_managed = False
                    continue
                if in_managed:
                    continue
                for kind, pattern in PATTERNS.items():
                    if pattern.search(stripped):
                        hits.append((lineno, kind, stripped.strip()))
                        break
    except OSError as exc:
        print(f"{path}: 読み取り失敗: {exc}", file=sys.stderr)
    return hits


def main(argv: list[str]) -> int:
    roots = argv[1:] or ["."]
    total = 0
    for root in roots:
        for path in sorted(iter_targets(root)):
            for lineno, kind, text in audit_file(path):
                total += 1
                print(f"{path}:{lineno}: {kind}: {text}")
    if total == 0:
        print("衝突しやすい記述は見つかりませんでした。")
        return 0
    print(f"\n{total} 件。各行について「不可逆操作の保護として今も必要か」を判断し、不要なら削除、必要なら理由を添えて書き直してください。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
