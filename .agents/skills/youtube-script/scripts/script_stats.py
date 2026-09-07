#!/usr/bin/env python3
"""YouTube 台本の尺を見積もり、構成上の問題を洗い出す。

使い方:
    python3 script_stats.py 台本.md
    python3 script_stats.py 台本.md --target 600            # 目標 10 分
    python3 script_stats.py 台本.md --target 45 --short     # ショート(フック 2 秒基準)
    python3 script_stats.py 台本.md --cpm 300 --wpm 140     # 話速を話者に合わせる

数え方:
  - `## 見出し` で章に分ける。見出しは尺に含めない。
  - 角括弧の指示(`[テロップ: ...]` `[B-roll: ...]` `[間]` など)、HTML コメント、
    コードブロック、引用行、箇条書きの記号、行頭の話者名は尺から除外する。
  - 日本語は「1 分あたりの文字数」、英語は「1 分あたりの語数」で換算し、合算する。
    既定は日本語 340 字/分、英語 150 語/分。これは目安であり、話者に合わせて変える。

問題があれば終了コード 1 を返す。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata

CJK = re.compile(
    r"[぀-ゟ゠-ヿ㐀-䶿一-鿿ｦ-ﾟ"
    r"々〆ー！？、。]"
)
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
BRACKET = re.compile(r"\[[^\[\]]*\]")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
SPEAKER = re.compile(r"^\s*[^\s:：]{1,12}[:：]\s*")
HEADING = re.compile(r"^(#{1,6})\s*(.*)$")
LIST_MARK = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SENTENCE_SPLIT = re.compile(r"(?<=[。．.!?！？])\s*")
HOOK_HINT = re.compile(r"フック|hook|冒頭|つかみ", re.IGNORECASE)
TODO = re.compile(r"\[要確認\]|\[TODO\]|\[未確認\]", re.IGNORECASE)


class Section:
    def __init__(self, title: str) -> None:
        self.title = title
        self.lines: list[str] = []
        self.raw_lines: list[str] = []

    @property
    def text(self) -> str:
        return " ".join(self.lines)

    def seconds(self, cpm: float, wpm: float) -> float:
        cjk = len(CJK.findall(self.text))
        words = len(LATIN_WORD.findall(self.text))
        return cjk / cpm * 60.0 + words / wpm * 60.0

    def counts(self) -> tuple[int, int]:
        return len(CJK.findall(self.text)), len(LATIN_WORD.findall(self.text))


def strip_narration(line: str) -> str | None:
    """ナレーションとして数える文字列を返す。数えない行は None。"""
    text = BRACKET.sub(" ", line)
    text = SPEAKER.sub("", text)
    text = LIST_MARK.sub("", text)
    text = re.sub(r"[*_`>|#]", " ", text)
    text = text.strip()
    return text or None


def parse(path: str) -> tuple[list[Section], list[tuple[int, str]]]:
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    body = HTML_COMMENT.sub(" ", body)
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        if end != -1:
            body = body[end + 5 :]

    sections = [Section("(冒頭)")]
    raw: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING.match(line)
        if heading:
            if len(heading.group(1)) == 2:
                sections.append(Section(heading.group(2).strip() or "(無題)"))
            continue
        raw.append((number, line))
        narration = strip_narration(line)
        if narration:
            sections[-1].lines.append(narration)
            sections[-1].raw_lines.append(line)
    if len(sections) > 1 and not sections[0].lines:
        sections.pop(0)
    return sections, raw


def width(text: str) -> int:
    """全角を 2 桁として数えた表示幅。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, columns: int) -> str:
    """表示幅で左詰めする。長すぎるものは省略記号で切る。"""
    if width(text) <= columns:
        return text + " " * (columns - width(text))
    out = ""
    for ch in text:
        if width(out) + width(ch) > columns - 1:
            break
        out += ch
    return out + "…" + " " * (columns - width(out) - 1)


def rpad(text: str, columns: int) -> str:
    """表示幅で右詰めする。"""
    return " " * max(0, columns - width(text)) + text


def fmt(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def long_sentences(sections: list[Section], limit: int) -> list[tuple[str, str]]:
    found = []
    for section in sections:
        for line in section.lines:
            for sentence in SENTENCE_SPLIT.split(line):
                stripped = sentence.strip()
                if len(stripped) > limit:
                    found.append((section.title, stripped))
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", help="台本の Markdown ファイル")
    parser.add_argument("--target", type=float, help="目標の尺(秒)")
    parser.add_argument("--tolerance", type=float, default=0.10, help="目標との許容差(既定 0.10 = ±10%%)")
    parser.add_argument("--cpm", type=float, default=340.0, help="日本語の話速(字/分、既定 340)")
    parser.add_argument("--wpm", type=float, default=150.0, help="英語の話速(語/分、既定 150)")
    parser.add_argument("--hook", type=float, help="フックの上限秒(既定: 長尺 15、--short 指定時 2)")
    parser.add_argument("--short", action="store_true", help="ショート/リールとして判定する")
    parser.add_argument("--max-sentence", type=int, default=60, help="一文の上限文字数(既定 60)")
    args = parser.parse_args(argv[1:])

    if not os.path.isfile(args.path):
        print(f"ファイルが見つかりません: {args.path}", file=sys.stderr)
        return 2

    sections, raw = parse(args.path)
    if not sections or not any(s.lines for s in sections):
        print("ナレーションとして数えられる行がありません。指示や見出しだけになっていないか確認してください。")
        return 1

    total = sum(s.seconds(args.cpm, args.wpm) for s in sections)
    print(f"{args.path}\n")
    print(pad("章", 36) + rpad("字", 6) + rpad("語", 6) + rpad("秒", 8) + rpad("割合", 7))
    print("-" * 63)
    for section in sections:
        seconds = section.seconds(args.cpm, args.wpm)
        cjk, words = section.counts()
        share = seconds / total * 100 if total else 0.0
        print(
            pad(section.title, 36)
            + rpad(str(cjk), 6)
            + rpad(str(words), 6)
            + rpad(fmt(seconds), 8)
            + rpad(f"{share:.0f}%", 7)
        )
    print("-" * 63)
    print(pad("合計", 36) + rpad("", 6) + rpad("", 6) + rpad(fmt(total), 8))
    print(f"\n話速: 日本語 {args.cpm:g} 字/分、英語 {args.wpm:g} 語/分(--cpm / --wpm で変更)")

    warnings: list[str] = []

    if args.target:
        delta = total - args.target
        low, high = args.target * (1 - args.tolerance), args.target * (1 + args.tolerance)
        verdict = "範囲内" if low <= total <= high else ("超過" if total > high else "不足")
        print(f"目標 {fmt(args.target)} に対して {fmt(total)}({delta:+.0f} 秒、{verdict})")
        if not low <= total <= high:
            need = abs(delta) / 60 * args.cpm
            action = "削る" if delta > 0 else "足す"
            warnings.append(f"尺が目標から外れています。日本語で約 {need:.0f} 字 {action}必要です。")

    hook_limit = args.hook if args.hook is not None else (2.0 if args.short else 15.0)
    hook = next((s for s in sections if HOOK_HINT.search(s.title)), sections[0])
    hook_seconds = hook.seconds(args.cpm, args.wpm)
    if hook_seconds > hook_limit:
        warnings.append(
            f"フック(「{hook.title}」)が {fmt(hook_seconds)} で上限 {hook_limit:g} 秒を超えています。"
        )

    for title, sentence in long_sentences(sections, args.max_sentence):
        preview = sentence if len(sentence) <= 46 else sentence[:45] + "…"
        warnings.append(f"一文が {len(sentence)} 字(上限 {args.max_sentence}): [{title}] {preview}")

    todos = [(number, line.strip()) for number, line in raw if TODO.search(line)]
    for number, line in todos:
        preview = line if len(line) <= 60 else line[:59] + "…"
        warnings.append(f"未確認の箇所が残っています(行 {number}): {preview}")

    if warnings:
        print("\n要対応:")
        for warning in warnings:
            print(f"  - {warning}")
        return 1
    print("\n要対応な点は見つかりませんでした。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
