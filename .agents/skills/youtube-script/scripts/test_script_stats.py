#!/usr/bin/env python3
"""script_stats.py の回帰テスト。標準ライブラリだけで動く。

    python3 test_script_stats.py

失敗があれば終了コード 1。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "script_stats.py")

sys.path.insert(0, HERE)
import script_stats as stats  # noqa: E402

FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    if actual == expected:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}: {actual!r} != {expected!r}")
        FAILURES.append(name)


def check_true(name: str, condition: bool, detail: str = "") -> None:
    check(name, bool(condition) or detail, True)


def run(body: str, *args: str) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as fh:
        fh.write(body)
        path = fh.name
    try:
        return subprocess.run(
            [sys.executable, TARGET, path, *args], capture_output=True, text=True
        )
    finally:
        os.unlink(path)


def main() -> int:
    speakers = stats.speaker_pattern(list(stats.DEFAULT_SPEAKERS))

    print("行番号: フロントマターと複数行コメントの後でもずれない")
    body = (
        "---\ntitle: t\n---\n\n<!--\nコメント\nが複数行\n-->\n\n"
        "## フック\n\n本文です。\n\n## 本編\n\n数字は要確認です。[要確認]\n"
    )
    result = run(body, "--target", "600")
    expected_line = body.splitlines().index("数字は要確認です。[要確認]") + 1
    check_true(
        f"[要確認] を行 {expected_line} と報告",
        f"行 {expected_line}" in result.stdout,
        result.stdout,
    )

    print("話者名: 指定した名前だけを剥がし、通常の文は削らない")
    check("進行役: を剥がす", stats.strip_narration("進行役: こんにちは", speakers), "こんにちは")
    check("話者A: を剥がす", stats.strip_narration("話者A: どうも", speakers), "どうも")
    check("コスト: は残す", stats.strip_narration("コスト:高い、しかし価値がある", speakers), "コスト:高い、しかし価値がある")
    check("結論: は残す", stats.strip_narration("結論: これです", speakers), "結論: これです")
    check_true(
        "URL を壊さない",
        "example.com" in (stats.strip_narration("https://example.com を見て", speakers) or ""),
        stats.strip_narration("https://example.com を見て", speakers),
    )
    check("--speakers 空で無効化", stats.speaker_pattern([""]), None)

    print("数字: 尺に反映される")
    section = stats.Section("t")
    section.lines.append("売上は12345円で30パーセント増")
    cjk, _ = section.counts()
    check_true(f"数字を数える (cjk={cjk})", cjk >= 18, cjk)
    check_true("秒数が 0 でない", section.seconds(340, 150) > 0)

    print("一文の長さ: 英語は語数で換算する")
    english = "This is a perfectly normal English sentence that runs about fourteen words long here."
    check_true(
        f"英文 {len(english)} 字は誤検出しない",
        stats.char_equivalent(english, 340, 150) <= 60,
        stats.char_equivalent(english, 340, 150),
    )
    japanese = "この文はわざと長くしていて、読点でつないだまま息継ぎの位置が分からなくなり、聞き手が主語を見失うことを確認するための例文です。"
    check_true(
        "長い日本語文は検出する",
        stats.char_equivalent(japanese, 340, 150) > 60,
        stats.char_equivalent(japanese, 340, 150),
    )

    print("除外と算入")
    check("角括弧の指示は除外", stats.strip_narration("[テロップ: あ]", speakers), None)
    check_true("引用行は算入", stats.strip_narration("> これは引用です。", speakers) == "これは引用です。")
    result = run("## 章\n\n```\nprint('code')\n```\n\n本文。\n")
    check_true("コードブロックを除外", "print" not in result.stdout, result.stdout)

    print("見出しなしの台本")
    result = run("見出しのない台本です。ここに本文だけがあります。\n", "--target", "600")
    warnings = result.stdout.split("要対応:")[-1]
    check_true("見出しなしを警告する", "`## 見出し` がないため" in warnings, warnings)
    check_true("フック超過は誤報告しない", "秒を超えています" not in warnings, warnings)

    print("終了コード")
    check("空ファイル", run("").returncode, 1)
    check("指示のみ", run("## 章\n[B-roll: x]\n").returncode, 1)
    check(
        "問題なし",
        run("## フック\n\n短い導入です。\n\n## 本編\n\n本文です。\n").returncode,
        0,
    )
    missing = subprocess.run([sys.executable, TARGET, "/nonexistent.md"], capture_output=True, text=True)
    check("存在しないファイル", missing.returncode, 2)

    print("見出しやコードブロック内の [要確認] も報告する")
    result = run("## 章 [要確認]\n\n本文です。\n")
    check_true("見出し内の [要確認]", "未確認の箇所" in result.stdout, result.stdout)

    if FAILURES:
        print(f"\n{len(FAILURES)} 件失敗: {', '.join(FAILURES)}")
        return 1
    print("\nすべて通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
