#!/usr/bin/env python3
"""既存のプロファイル(ハウススタイル)を探して読み込む。

使い方:
    python3 load_house_style.py                 # カレントから上へ探して要約を表示
    python3 load_house_style.py --root ~/vault  # 探索の起点を指定
    python3 load_house_style.py --json          # copy_check.py に渡す JSON を出力

探すもの(Second Brain 形式):
    00_システム/00_UserProfile/*.md   一人称・語尾・NGワード・構成テンプレ
    コンテキスト.md                    ミッション、対象読者、コンテンツ構成テンプレ
    .agent/skills/my_writer/          文体注入スキル(あれば文体はそちらに委ねる)

見つからなければ「汎用モード」を返す。その場合はスキル同梱の一般則で書く。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

PROFILE_DIR = os.path.join("00_システム", "00_UserProfile")
MARKERS = (PROFILE_DIR, "コンテキスト.md", os.path.join(".agent", "skills", "my_writer"))

FIELD_PATTERNS = {
    "first_person": re.compile(r"一人称\**\s*[:：]\s*\**\s*([^\n*]+)"),
    "second_person": re.compile(r"二人称\**\s*[:：]\s*\**\s*([^\n*]+)"),
    "tone": re.compile(r"基本トーン\**\s*[:：]\s*\**\s*([^\n]+)"),
    "structure_template": re.compile(r"コンテンツ構成テンプレ\**\s*[:：]\s*\**\s*([^\n]+)"),
}
NG_SECTION = re.compile(r"\*\*(NGワード|Forbidden Terms[^*]*|使用禁止用語)\*\*[^\n]*\n((?:[ \t]*[*\-][^\n]*\n?)+)", re.M)
NG_INLINE = re.compile(r"\*\*NGワード\**\s*[:：]\s*\**\s*([^\n]+)")
TERM_SPLIT = re.compile(r"[、,／/]|\s{2,}")


def find_root(start: str) -> str | None:
    """マーカーを含むディレクトリを、起点から上へ辿って探す。"""
    current = os.path.abspath(start)
    while True:
        if any(os.path.exists(os.path.join(current, marker)) for marker in MARKERS):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def clean_terms(blob: str) -> list[str]:
    terms = []
    for raw in TERM_SPLIT.split(blob):
        term = raw.strip().strip("*-`。 、").strip()
        term = re.sub(r"^\s*[*\-]\s*", "", term)
        if term and len(term) <= 24 and not term.startswith("("):
            terms.append(term)
    return terms


def collect(root: str) -> dict:
    profile_dir = os.path.join(root, PROFILE_DIR)
    files = []
    if os.path.isdir(profile_dir):
        files = [os.path.join(profile_dir, n) for n in sorted(os.listdir(profile_dir)) if n.endswith(".md")]
    context = os.path.join(root, "コンテキスト.md")
    if os.path.isfile(context):
        files.append(context)

    blob = "\n".join(read(path) for path in files)
    found: dict = {"root": root, "files": [os.path.relpath(p, root) for p in files], "mode": "house"}

    for key, pattern in FIELD_PATTERNS.items():
        match = pattern.search(blob)
        if match:
            found[key] = match.group(1).strip().strip("*。 ")

    forbidden: list[str] = []
    for _, body in NG_SECTION.findall(blob):
        for line in body.splitlines():
            forbidden.extend(clean_terms(line))
    for inline in NG_INLINE.findall(blob):
        forbidden.extend(clean_terms(inline))
    seen: dict[str, None] = {}
    for term in forbidden:
        seen.setdefault(term, None)
    found["forbidden_terms"] = list(seen)

    writer = os.path.join(root, ".agent", "skills", "my_writer")
    found["style_skill"] = os.path.relpath(writer, root) if os.path.isdir(writer) else None
    injector = os.path.join(writer, "scripts", "style_injector.py")
    found["style_command"] = (
        f"python3 {os.path.relpath(injector, root)} --topic \"<トピック>\"" if os.path.isfile(injector) else None
    )
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="探索の起点(既定: カレント)")
    parser.add_argument("--json", action="store_true", help="JSON で出力する")
    args = parser.parse_args(argv[1:])

    root = find_root(args.root)
    if root is None:
        result = {"mode": "generic", "root": None, "files": [], "forbidden_terms": []}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("ハウススタイルは見つかりませんでした(汎用モード)。")
            print("スキル同梱の一般則で書きます。既存の文体規定があるなら --root で場所を指定してください。")
        return 0

    result = collect(root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"ハウススタイルを検出しました: {result['root']}\n")
    print("参照したファイル:")
    for name in result["files"]:
        print(f"  - {name}")
    print()
    for key, label in (
        ("tone", "基本トーン"),
        ("first_person", "一人称"),
        ("second_person", "二人称"),
        ("structure_template", "構成テンプレ"),
    ):
        if result.get(key):
            print(f"{label}: {result[key]}")
    if result["forbidden_terms"]:
        print(f"禁止・NG ワード({len(result['forbidden_terms'])}): {'、'.join(result['forbidden_terms'])}")
    if result["style_command"]:
        print(f"\n文体はこのスキルで注入する: {result['style_command']}")
        print("型(構成・媒体別ルール)はこちらで持ち、文体は上記に委ねる。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
