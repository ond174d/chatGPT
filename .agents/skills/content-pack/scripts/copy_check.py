#!/usr/bin/env python3
"""概要欄・SNS 投稿・キャプションを、文字数上限とハウススタイルに照らして点検する。

使い方:
    python3 copy_check.py 原稿.txt --platform youtube-description
    python3 copy_check.py 投稿.txt --platform x            # 日本語は 2 文字分で数える
    python3 copy_check.py 一式.md  --platform auto         # `## platform: x` の見出しで切り替え
    echo "本文" | python3 copy_check.py - --platform instagram
    python3 copy_check.py 原稿.txt --platform x --style-root ~/vault   # 禁止語をそこから読む

見るもの:
  - 文字数の上限。X は CJK を 2 単位として数える(公式の重み付けに合わせる)。
  - 「続きを読む」前に見える範囲に、要点が入っているか。
  - ハウススタイルの禁止・NG ワード(load_house_style.py が拾ったもの)。
  - 断定を求める文体のときの弱い語尾(〜と思います など)。--no-hedge-check で無効化。
  - Instagram のハッシュタグ数。

上限超過や禁止語があれば終了コード 1。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys


def _utf8_stdout() -> None:
    """Windows の既定エンコーディング(cp932 など)で日本語が落ちるのを防ぐ。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


HERE = os.path.dirname(os.path.abspath(__file__))
LIMITS_PATH = os.path.join(os.path.dirname(HERE), "assets", "limits.json")

# X の重み付け: CJK・かな・全角記号は 2 単位。
# ソースを ASCII に保つため \u エスケープで書く(cp932 環境での再保存に強い)。
WEIGHTED_2 = re.compile(
    "[\\u3040-\\u309f\\u30a0-\\u30ff\\u3400-\\u4dbf\\u4e00-\\u9fff\\uff66-\\uff9f"
    "\\uff01-\\uff60\\u3001\\u3002\\u3005\\u3006\\u30fc]"
)
HASHTAG = re.compile(r"[#＃][^\s#＃]+")
PLATFORM_HEADING = re.compile(r"^##\s*platform\s*[:：]\s*([a-z0-9\-]+)\s*$", re.I | re.M)
HEDGE = re.compile(r"と思います|かもしれません|ではないでしょうか|気がします|だと思う")


def load_limits() -> dict:
    with open(LIMITS_PATH, encoding="utf-8") as fh:
        return json.load(fh)["platforms"]


def weighted_length(text: str) -> int:
    return len(text) + len(WEIGHTED_2.findall(text))


def load_style(root: str | None) -> dict:
    sys.path.insert(0, HERE)
    import load_house_style as house  # noqa: E402

    found = house.find_root(root or ".")
    if found is None:
        return {"mode": "generic", "forbidden_terms": []}
    return house.collect(found)


def split_sections(body: str) -> list[tuple[str, str]]:
    """`## platform: x` 見出しで分割する。見出しが無ければ全体を 1 つとして返す。"""
    matches = list(PLATFORM_HEADING.finditer(body))
    if not matches:
        return [("", body)]
    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections.append((match.group(1).lower(), body[start:end].strip()))
    return sections


def check(name: str, text: str, spec: dict, style: dict, hedge_check: bool) -> list[str]:
    problems: list[str] = []
    limit = spec["limit"]
    length = weighted_length(text) if spec.get("weighted") else len(text)
    unit = "単位(日本語は 2 単位)" if spec.get("weighted") else "字"
    status = "超過" if length > limit else "範囲内"
    print(f"  {spec['label']}: {length} / {limit} {unit} ... {status}")
    if length > limit:
        problems.append(f"{spec['label']}が {length - limit} {unit}超過しています。")

    visible = spec.get("visible")
    if visible and len(text) > visible:
        head = text[:visible].replace("\n", " ")
        preview = head if len(head) <= 50 else head[:49] + "…"
        print(f"    冒頭 {visible} 字(続きを読む前に見える範囲): {preview}")

    if spec.get("max_hashtags") is not None:
        tags = HASHTAG.findall(text)
        print(f"    ハッシュタグ: {len(tags)} / {spec['max_hashtags']}")
        if len(tags) > spec["max_hashtags"]:
            problems.append(f"ハッシュタグが {len(tags)} 個で上限 {spec['max_hashtags']} を超えています。")

    for term in style.get("forbidden_terms", []):
        if re.search(re.escape(term), text, re.IGNORECASE):
            problems.append(f"禁止・NG ワード「{term}」が含まれています。")

    if hedge_check and style.get("mode") == "house":
        tone = style.get("tone", "")
        if "言い切り" in tone or "断言" in tone:
            for match in HEDGE.finditer(text):
                start = max(0, match.start() - 12)
                problems.append(f"言い切り型の文体に対して弱い語尾: …{text[start:match.end()]}")
    return problems


def main(argv: list[str]) -> int:
    _utf8_stdout()
    limits = load_limits()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="点検するファイル。- で標準入力")
    parser.add_argument(
        "--platform", default="auto",
        choices=("auto", *sorted(limits)), help="対象プラットフォーム。auto は見出しから判定",
    )
    parser.add_argument("--style-root", help="ハウススタイルの探索起点(既定: カレントから上へ探す)")
    parser.add_argument("--no-hedge-check", action="store_true", help="弱い語尾の検出をしない")
    args = parser.parse_args(argv[1:])

    if args.path == "-":
        body = sys.stdin.read()
        label = "(標準入力)"
    else:
        if not os.path.isfile(args.path):
            print(f"ファイルが見つかりません: {args.path}", file=sys.stderr)
            return 2
        with open(args.path, encoding="utf-8") as fh:
            body = fh.read()
        label = args.path

    style = load_style(args.style_root)
    print(f"{label}")
    if style.get("mode") == "house":
        print(f"ハウススタイル: {style['root']}(禁止語 {len(style['forbidden_terms'])} 件)")
    else:
        print("ハウススタイル: 未検出(汎用モード)")
    print()

    sections = split_sections(body)
    if args.platform != "auto":
        sections = [(args.platform, body.strip())]

    problems: list[str] = []
    checked = 0
    for name, text in sections:
        if not name:
            print("プラットフォームを判定できません。--platform で指定するか、`## platform: x` の見出しを付けてください。")
            return 2
        spec = limits.get(name)
        if spec is None:
            problems.append(f"未知のプラットフォーム「{name}」。limits.json に定義がありません。")
            continue
        if not text:
            problems.append(f"{spec['label']}の本文が空です。")
            continue
        checked += 1
        problems.extend(check(name, text, spec, style, not args.no_hedge_check))

    if not checked and not problems:
        print("点検対象がありませんでした。")
        return 1
    if problems:
        print("\n要対応:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\n要対応な点は見つかりませんでした。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
