#!/usr/bin/env python3
"""content-pack のスクリプトの回帰テスト。標準ライブラリだけで動く。

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
COPY_CHECK = os.path.join(HERE, "copy_check.py")

sys.path.insert(0, HERE)
import script_stats as stats  # noqa: E402
import copy_check as copy  # noqa: E402
import load_house_style as house  # noqa: E402

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

    test_copy_check()
    test_house_style()
    test_windows_safety()

    if FAILURES:
        print(f"\n{len(FAILURES)} 件失敗: {', '.join(FAILURES)}")
        return 1
    print("\nすべて通過")
    return 0


def test_windows_safety() -> None:
    print("Windows: cp932 の標準出力でも落ちない")
    body = "## 本編 1 \u2014 見出し\n\n\u2014 を含む本文です。\n"
    path = write_temp(body)
    env = dict(os.environ, PYTHONIOENCODING="cp932")
    try:
        for name, argv in (
            ("script_stats", [TARGET, path, "--target", "60"]),
            ("copy_check", [COPY_CHECK, path, "--platform", "youtube-description"]),
        ):
            done = subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=env)
            check_true(f"{name} が cp932 で例外を出さない", "UnicodeEncodeError" not in done.stderr, done.stderr)
            check_true(f"{name} が出力を返す", bool(done.stdout.strip()), done.stdout)
    finally:
        os.unlink(path)

    print("Windows: スクリプトのソースが cp932 で表現できる")
    for name in ("script_stats.py", "copy_check.py", "load_house_style.py"):
        text = open(os.path.join(HERE, name), encoding="utf-8").read()
        try:
            text.encode("cp932")
            ok = True
        except UnicodeEncodeError:
            ok = False
        check_true(f"{name} は cp932 で保存できる", ok)

    print("Windows: install.py のインタプリタ判定")
    import importlib.util

    install_path = os.path.abspath(
        os.path.join(HERE, "..", "..", "astra-riding", "scripts", "install.py")
    )
    if not os.path.isfile(install_path):
        print("  skip install.py (見つからない)")
        return
    spec = importlib.util.spec_from_file_location("install_under_test", install_path)
    install = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(install)

    check("POSIX の既定", install.python_command() if os.name != "nt" else "python3", "python3")
    check("明示指定が勝つ", install.python_command("py -3.12"), "py -3.12")

    real_name, real_which = os.name, install.shutil.which
    try:
        os.name = "nt"
        install.shutil.which = lambda name: "py.exe" if name == "py" else None
        check("Windows で py があれば py -3", install.python_command(), "py -3")
        install.shutil.which = lambda name: None
        check("Windows で py が無ければ python", install.python_command(), "python")
        command = install.hook_command(os.path.join("/p", ".claude", "hooks"), "/p", "py -3")
        check("フックのパスはスラッシュ区切り", command, "py -3 .claude/hooks/rulecard_hook.py")
    finally:
        os.name, install.shutil.which = real_name, real_which


def write_temp(body: str, suffix: str = ".md") -> str:
    with tempfile.NamedTemporaryFile("w", suffix=suffix, encoding="utf-8", delete=False) as fh:
        fh.write(body)
        return fh.name


def run_copy(body: str, *args: str) -> subprocess.CompletedProcess:
    path = write_temp(body)
    try:
        return subprocess.run([sys.executable, COPY_CHECK, path, *args], capture_output=True, text=True)
    finally:
        os.unlink(path)


def test_copy_check() -> None:
    print("copy_check: X の重み付け(日本語は 2 単位)")
    check("かな 10 文字 = 20 単位", copy.weighted_length("あ" * 10), 20)
    check("英字 10 文字 = 10 単位", copy.weighted_length("abcdefghij"), 10)
    check("混在", copy.weighted_length("あa" * 5), 15)
    check("全角記号も 2 単位", copy.weighted_length("。、ー々"), 8)

    print("copy_check: 上限判定")
    over = run_copy("あ" * 141, "--platform", "x", "--style-root", tempfile.gettempdir())
    check_true("X 141 字は超過", "超過" in over.stdout, over.stdout)
    check("超過は終了コード 1", over.returncode, 1)
    under = run_copy("あ" * 100, "--platform", "x", "--style-root", tempfile.gettempdir())
    check("範囲内は終了コード 0", under.returncode, 0)

    print("copy_check: 見出しでプラットフォームを切り替える")
    body = "## platform: youtube-title\n\nタイトル\n\n## platform: x\n\n投稿本文です。\n"
    result = run_copy(body, "--platform", "auto", "--style-root", tempfile.gettempdir())
    check_true("2 媒体を点検", "YouTube タイトル" in result.stdout and "X 投稿" in result.stdout, result.stdout)
    check("両方範囲内なら 0", result.returncode, 0)

    print("copy_check: ハッシュタグ数")
    tags = " ".join(f"#タグ{i}" for i in range(31))
    result = run_copy(tags, "--platform", "instagram", "--style-root", tempfile.gettempdir())
    check_true("31 個で警告", "ハッシュタグが 31 個" in result.stdout, result.stdout)

    print("copy_check: 空・未知・不明")
    check("空の本文", run_copy("", "--platform", "x", "--style-root", tempfile.gettempdir()).returncode, 1)
    result = run_copy("本文\n", "--platform", "auto", "--style-root", tempfile.gettempdir())
    check("見出しなしで auto は 2", result.returncode, 2)
    missing = subprocess.run([sys.executable, COPY_CHECK, "/nonexistent.txt", "--platform", "x"], capture_output=True, text=True)
    check("存在しないファイル", missing.returncode, 2)


def test_house_style() -> None:
    print("load_house_style: 検出と汎用フォールバック")
    root = tempfile.mkdtemp()
    profile = os.path.join(root, "00_システム", "00_UserProfile")
    os.makedirs(profile)
    with open(os.path.join(profile, "03_style.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "## 1. Voice & Tone\n"
            "*   **基本トーン**: 「〜だ」の言い切り型を基本とする。\n"
            "*   **一人称**: 私\n"
            "*   **二人称**: あなた\n"
            "*   **Forbidden Terms (使用禁止用語)**\n"
            "    *   API, Python, JSON\n"
        )
    with open(os.path.join(root, "コンテキスト.md"), "w", encoding="utf-8") as fh:
        fh.write("- **コンテンツ構成テンプレ**: Hook / Prove / Teach / Entertain / Action の5ブロック\n")

    found = house.collect(house.find_root(root))
    check("モード", found["mode"], "house")
    check("一人称", found.get("first_person"), "私")
    check_true("言い切り型を拾う", "言い切り" in found.get("tone", ""), found.get("tone"))
    check_true("構成テンプレを拾う", "Hook" in found.get("structure_template", ""), found.get("structure_template"))
    for term in ("API", "Python", "JSON"):
        check_true(f"禁止語 {term}", term in found["forbidden_terms"], found["forbidden_terms"])

    nested = os.path.join(root, "a", "b")
    os.makedirs(nested)
    check("下位ディレクトリからも見つける", house.find_root(nested), root)
    check("マーカーが無ければ None", house.find_root(tempfile.mkdtemp()), None)

    print("copy_check: ハウススタイルの禁止語と弱い語尾")
    result = run_copy("Python で自動化できると思います。", "--platform", "x", "--style-root", root)
    check_true("禁止語を検出", "「Python」" in result.stdout, result.stdout)
    check_true("弱い語尾を検出", "弱い語尾" in result.stdout, result.stdout)
    clean = run_copy("業務のどこで使うかを決めるのが先だ。", "--platform", "x", "--style-root", root)
    check("問題なしなら 0", clean.returncode, 0)
    off = run_copy(
        "自動化できると思います。", "--platform", "x", "--style-root", root, "--no-hedge-check"
    )
    check_true("--no-hedge-check で無効化", "弱い語尾" not in off.stdout, off.stdout)


if __name__ == "__main__":
    sys.exit(main())
