#!/usr/bin/env python3
"""YouTube 台本の尺を見積もり、構成上の問題を洗い出す。

使い方:
    python3 script_stats.py 台本.md
    python3 script_stats.py 台本.md --target 600            # 目標 10 分
    python3 script_stats.py 台本.md --target 45 --short     # ショート(フック 2 秒基準)
    python3 script_stats.py 台本.md --cpm 300 --wpm 140     # 話速を話者に合わせる
    python3 script_stats.py 台本.md --speakers 進行役,ゲスト  # 行頭の話者名を尺から除く

数え方:
  - `## 見出し` で章に分ける。見出し自体は尺に含めない。
  - 尺から除外するもの: 角括弧の指示(`[テロップ: ...]` `[間]` など)、HTML コメント
    (複数行も可)、コードブロック、先頭の YAML フロントマター、箇条書きや強調の記号、
    `--speakers` で指定した行頭の話者名。
  - 尺に含めるもの: 引用行(`>`)と表の中の文字。読み上げる可能性があるため数える。
    除きたい場合はコメントか角括弧に入れる。
  - 日本語(漢字・かな・全角記号)と算用数字は「1 分あたりの文字数」、英単語は
    「1 分あたりの語数」で換算して合算する。既定は日本語 340 字/分、英語 150 語/分。
    これは目安であり、話者に合わせて --cpm / --wpm で変える。

問題があれば終了コード 1、ファイルが読めなければ 2 を返す。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata


def _utf8_stdout() -> None:
    """Windows の既定エンコーディング(cp932 など)で日本語が落ちるのを防ぐ。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


# 日本語として 1 文字ずつ数える範囲。算用数字も読み上げに時間がかかるので含める。
# ひらがな・カタカナ・漢字・半角カナ・全角記号・算用数字。
# ソースを ASCII に保つため \u エスケープで書く(cp932 環境での再保存に強い)。
CJK = re.compile(
    "[\\u3040-\\u309f\\u30a0-\\u30ff\\u3400-\\u4dbf\\u4e00-\\u9fff\\uff66-\\uff9f"
    "\\u3005\\u3006\\u30fc\\uff01\\uff1f\\u3001\\u30020-9\\uff10-\\uff19\\uff05\\u301c]"
)
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
BRACKET = re.compile(r"\[[^\[\]]*\]")
COMMENT_OPEN = "<!--"
COMMENT_CLOSE = "-->"
INLINE_COMMENT = re.compile(r"<!--.*?-->")
HEADING = re.compile(r"^(#{1,6})\s*(.*)$")
LIST_MARK = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SENTENCE_SPLIT = re.compile(r"(?<=[。．.!?！？])\s*")
HOOK_HINT = re.compile(r"フック|hook|冒頭|つかみ", re.IGNORECASE)
TODO = re.compile(r"\[要確認\]|\[TODO\]|\[未確認\]", re.IGNORECASE)
DEFAULT_SPEAKERS = ("進行役", "ゲスト", "司会", "インタビュアー", "ナレーション", "N")
SPEAKER_SUFFIX = r"\s*[:：]\s*"


def speaker_pattern(names: list[str]) -> re.Pattern[str] | None:
    """行頭の話者名だけを剥がす。`結論:` や URL を誤って削らないよう、名前を限定する。"""
    names = [name.strip() for name in names if name.strip()]
    if not names:
        return None
    alternatives = "|".join(re.escape(name) for name in names)
    return re.compile(rf"^\s*(?:{alternatives}|話者[A-Za-z0-9]{{0,3}}|[A-Z]){SPEAKER_SUFFIX}")


class Section:
    def __init__(self, title: str) -> None:
        self.title = title
        self.lines: list[str] = []

    @property
    def text(self) -> str:
        return " ".join(self.lines)

    def counts(self) -> tuple[int, int]:
        return len(CJK.findall(self.text)), len(LATIN_WORD.findall(self.text))

    def seconds(self, cpm: float, wpm: float) -> float:
        cjk, words = self.counts()
        return cjk / cpm * 60.0 + words / wpm * 60.0


def strip_narration(line: str, speakers: re.Pattern[str] | None) -> str | None:
    """ナレーションとして数える文字列を返す。数えない行は None。"""
    text = BRACKET.sub(" ", line)
    if speakers is not None:
        text = speakers.sub("", text, count=1)
    text = LIST_MARK.sub("", text)
    text = re.sub(r"[*_`>|#]", " ", text)
    text = text.strip()
    return text or None


def parse(path: str, speakers: re.Pattern[str] | None) -> tuple[list[Section], list[tuple[int, str]]]:
    """章の一覧と、(行番号, 原文) の一覧を返す。行番号は元ファイルの番号のまま。"""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    sections = [Section("(冒頭)")]
    raw: list[tuple[int, str]] = []
    in_fence = False
    in_comment = False
    in_frontmatter = bool(lines) and lines[0].strip() == "---"

    for number, line in enumerate(lines, 1):
        raw.append((number, line))

        if in_frontmatter:
            if number > 1 and line.strip() == "---":
                in_frontmatter = False
            continue

        text = line
        if in_comment:
            if COMMENT_CLOSE in text:
                text = text.split(COMMENT_CLOSE, 1)[1]
                in_comment = False
            else:
                continue
        text = INLINE_COMMENT.sub(" ", text)
        if COMMENT_OPEN in text:
            text = text.split(COMMENT_OPEN, 1)[0]
            in_comment = True

        if text.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading = HEADING.match(text)
        if heading:
            if len(heading.group(1)) == 2:
                sections.append(Section(heading.group(2).strip() or "(無題)"))
            continue

        narration = strip_narration(text, speakers)
        if narration:
            sections[-1].lines.append(narration)

    if len(sections) > 1 and not sections[0].lines:
        sections.pop(0)
    return sections, raw


def width(text: str) -> int:
    """全角を 2 桁として数えた表示幅。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, columns: int) -> str:
    if width(text) <= columns:
        return text + " " * (columns - width(text))
    out = ""
    for ch in text:
        if width(out) + width(ch) > columns - 1:
            break
        out += ch
    return out + "…" + " " * (columns - width(out) - 1)


def rpad(text: str, columns: int) -> str:
    return " " * max(0, columns - width(text)) + text


def fmt(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def char_equivalent(text: str, cpm: float, wpm: float) -> int:
    """英単語を日本語の文字数に換算した長さ。英文だけの文が誤検出されるのを防ぐ。"""
    cjk = len(CJK.findall(text))
    words = len(LATIN_WORD.findall(text))
    return cjk + int(round(words * cpm / wpm))


def long_sentences(sections: list[Section], limit: int, cpm: float, wpm: float) -> list[tuple[str, str, int]]:
    found = []
    for section in sections:
        for line in section.lines:
            for sentence in SENTENCE_SPLIT.split(line):
                stripped = sentence.strip()
                length = char_equivalent(stripped, cpm, wpm)
                if length > limit:
                    found.append((section.title, stripped, length))
    return found


def main(argv: list[str]) -> int:
    _utf8_stdout()
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
    parser.add_argument("--max-sentence", type=int, default=60, help="一文の上限(日本語換算の文字数、既定 60)")
    parser.add_argument(
        "--speakers",
        default=",".join(DEFAULT_SPEAKERS),
        help="行頭で剥がす話者名をカンマ区切りで指定(既定: %(default)s)。空文字で無効化",
    )
    args = parser.parse_args(argv[1:])

    if not os.path.isfile(args.path):
        print(f"ファイルが見つかりません: {args.path}", file=sys.stderr)
        return 2

    speakers = speaker_pattern(args.speakers.split(","))
    sections, raw = parse(args.path, speakers)
    if not any(section.lines for section in sections):
        print("ナレーションとして数えられる行がありません。指示や見出しだけになっていないか確認してください。")
        return 1

    total = sum(section.seconds(args.cpm, args.wpm) for section in sections)
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

    titled = [s for s in sections if s.title != "(冒頭)"]
    if not titled:
        warnings.append("`## 見出し` がないため章に分けられません。章ごとの配分とフックの判定ができません。")
    else:
        hook_limit = args.hook if args.hook is not None else (2.0 if args.short else 15.0)
        hook = next((s for s in titled if HOOK_HINT.search(s.title)), titled[0])
        hook_seconds = hook.seconds(args.cpm, args.wpm)
        if hook_seconds > hook_limit:
            warnings.append(
                f"フック(「{hook.title}」)が {fmt(hook_seconds)} で上限 {hook_limit:g} 秒を超えています。"
            )

    for title, sentence, length in long_sentences(sections, args.max_sentence, args.cpm, args.wpm):
        preview = sentence if len(sentence) <= 46 else sentence[:45] + "…"
        warnings.append(f"一文が {length} 字相当(上限 {args.max_sentence}): [{title}] {preview}")

    for number, line in raw:
        if TODO.search(line):
            stripped = line.strip()
            preview = stripped if len(stripped) <= 60 else stripped[:59] + "…"
            warnings.append(f"未確認の箇所が残っています(行 {number}): {preview}")

    if warnings:
        print("\n要対応:")
        for warning in warnings:
            print(f"  - {warning}")
        return 1
    print("\n要対応な点は見つかりませんでした。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except BrokenPipeError:
        # `| head` などで途中終了したとき。エラーを出さずに終える。
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
