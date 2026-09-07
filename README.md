# skills

エージェント用スキルの置き場。2 つ入っている。

| スキル | 中身 |
| --- | --- |
| [astra-riding](.agents/skills/astra-riding/) | 判断様式そのもの。どう判断して進めるかを規定する |
| [content-pack](.agents/skills/content-pack/) | 動画台本と、概要欄・SNS 投稿・キャプションまで一式を完成品として書く。進め方は astra-riding に従う |

---

## astra-riding

エージェントの**判断様式そのもの**を配布するスキル。何を作るかではなく、どう判断して進めるかを規定する。
GPT-6 Astra が Codex 上で見せる振る舞い(公開されている組み込み指示から抽出)を出発点に、
モデルにもエージェントにも作業分野にも依存しない形へ一般化してある。

コードの実装・デバッグ・レビューだけでなく、調査、分析、文章作成、資料作成、データ処理、
運用作業、意思決定の支援にそのまま使える。

### 何が変わるか

- 「できますか」で止まらず、依頼として実行し、最後まで仕上げる。
- 結果を左右する問いだけを聞き、待つ間も手を止めない。推測できる細部は自分で決め、前提として伝える。
- 許可を求めるのは取り消せない操作と外部に影響する操作だけ。しかも承認が最後の一手になるまで作業を済ませてから聞く。
- このセッションで実際に見たものだけを事実として述べ、確認できなかったことを先に言う。
- 検証は影響に比例させる。報告は結論から。

### 構成

```
.agents/skills/astra-riding/
├── SKILL.md                       # 8 原則と 6 ステップの判断ループ、依頼の 5 型
├── agents/openai.yaml             # Codex UI 用メタデータ
├── references/
│   ├── decision-rules.md          # 許可・質問・前提・検証の基準と文例
│   ├── task-types.md              # 依頼の型と、分野別(コード/調査/文章/データ/運用/意思決定)の当てはめ
│   ├── writing-style.md           # 文体、最終報告、PR 説明
│   ├── harness-setup.md           # 各エージェントへの常時適用(4 層モデル)
│   ├── codex-setup.md             # Codex での Astra 設定、推論強度
│   ├── astra-on-sol-terra.md      # Astra を使わず GPT-5.6 Sol / Terra で同じ振る舞いを出す
│   └── sources.md                 # 出典
├── assets/
│   ├── overlay.md                 # 指示ファイルに埋め込む判断規則の本体
│   ├── rulecard.md                # 11 行に圧縮した規則カード(hooks が注入)
│   ├── hooks/rulecard_hook.py     # セッション開始時・圧縮後の再注入(エージェント非依存)
│   ├── claude/                    # CLAUDE.md 用 hooks 設定、検証サブエージェント
│   └── codex/                     # プロファイル、全置換指示、hooks、検証サブエージェント
└── scripts/
    ├── install.py                 # Claude Code / Codex / AGENTS.md へ導入(管理ブロック方式)
    └── audit_instructions.py      # 原則と衝突する記述の洗い出し
```

### 使い方

#### スキルとして呼ぶ

Claude Code なら `/astra-riding`、Codex なら `$astra-riding`。「Astra 流で」「最後までやって」でも作動する。
このリポジトリでは `.claude/skills/astra-riding` と `.agents/skills/astra-riding` の両方から読める。

他のプロジェクトで使うなら、スキルディレクトリへコピーする。

```bash
cp -rL .agents/skills/astra-riding ~/.claude/skills/    # Claude Code
cp -r  .agents/skills/astra-riding ~/.agents/skills/    # Codex ほか
```

#### 常時適用する(推奨)

指示ファイル・hooks・検証サブエージェントとして環境に埋め込む。使っているエージェントは自動判別される。

```bash
python3 .agents/skills/astra-riding/scripts/install.py --project              # このプロジェクトへ
python3 .agents/skills/astra-riding/scripts/install.py --project --target all # claude + codex + AGENTS.md
python3 .agents/skills/astra-riding/scripts/install.py --global --with-skill  # ユーザー全体へ、スキル本体ごと
python3 .agents/skills/astra-riding/scripts/install.py --project --dry-run    # 予定だけ表示
```

すべて管理ブロック方式で、再実行すれば中身だけ更新され、手書き部分は残る。既存ファイルはバックアップを取る。
詳細は `references/harness-setup.md`。

#### 指示ファイルの監査

```bash
python3 .agents/skills/astra-riding/scripts/audit_instructions.py .
```

AGENTS.md / CLAUDE.md / GEMINI.md / SKILL.md / `.cursorrules` / `.cursor/rules/*.mdc` /
`.github/copilot-instructions.md` を走査し、「常に確認する」「決して〜しない」型の記述を一覧にする。
自律動作を止めやすい古い指示を見つけるためのもの。

#### Astra を使わずに Sol / Terra で動かす

```bash
python3 .agents/skills/astra-riding/scripts/install.py --project --target codex
codex --profile astra-sol      # または astra-terra / astra-sol-full / astra-terra-full
```

Astra だけが持つ判断規則を Sol / Terra の組み込み指示の上に重ね、hooks で再注入し、
引き渡し前に `$astra-verifier` で主張と成果物を突き合わせる。詳細は `references/astra-on-sol-terra.md`。

---

## content-pack

動画台本と、それに付随する公開用テキスト一式を**完成品**として書くスキル。
台本(長尺・ショート・対談)、YouTube のタイトル・概要欄・チャプター・固定コメント、
X / Instagram / TikTok の投稿文とキャプション、サムネイル文言。
進め方は astra-riding の判断ループをそのまま使う。

### 2 つのモード

書き始める前に既存のプロファイルを探し、見つかればそちらに従う。

| モード | 条件 | 文体 | 構成 |
| --- | --- | --- | --- |
| ハウス | `00_システム/00_UserProfile/` や `コンテキスト.md` がある | プロファイルの規定。文体注入スキルがあれば委ねる | プロファイルの構成テンプレート |
| 汎用 | 見つからない | 同梱の一般則 | 同梱の一般型 |

ハウスモードでは、このスキルが持つのは**型と検証だけ**で、文体はプロファイル側に残す。
既存の責務分離(文体はスキル、型はワークフロー)を壊さないための設計。

```bash
python3 .agents/skills/content-pack/scripts/load_house_style.py
```

一人称、二人称、基本トーン、構成テンプレート、禁止用語、文体注入スキルの実行コマンドを検出する。

### この分野で効く astra-riding の規則

- 「台本を作って」を構成案の依頼と解釈しない。実際に話す文まで書き切る。
- 尺と視聴者だけを先に聞き、残りは前提を置いて進む。答えを待つ間も手を止めない。
- 数字・日付・価格・統計は、確認できたものだけを断定形で書く。確認できないものは `[要確認]` を付けて公開前に潰す。
- 確証がないときに語尾だけ言い切りに変えない。強めるのではなく主張を落とす。

### 構成

```
.agents/skills/content-pack/
├── SKILL.md                      # ハウススタイル確認 → 5 項目確定 → 7 ステップ
├── agents/openai.yaml
├── references/
│   ├── house-style.md            # 2 モード、責務分離、5 ブロック構成への対応
│   ├── structure.md              # 尺別の配分、フックの型、離脱を防ぐ設計、ショート
│   ├── formats.md                # 解説/レビュー/チュートリアル/ニュース/検証/対談/vlog/案件
│   ├── delivery.md               # 話し言葉への直し方、間、画面指示の記法
│   ├── derivatives.md            # タイトル/概要欄/チャプター/固定コメント/X/IG/TikTok/サムネ
│   └── checklist.md              # 納品前チェック
├── assets/
│   ├── template-long.md          # 長尺テンプレート
│   ├── template-short.md         # ショート/リールテンプレート
│   ├── template-interview.md     # 対談の進行台本テンプレート
│   ├── template-derivatives.md   # 公開用テキスト一式テンプレート
│   └── limits.json               # 媒体別の文字数上限(出典付き)
└── scripts/
    ├── load_house_style.py       # 既存プロファイルの検出
    ├── script_stats.py           # 尺の見積り、章ごとの配分、長文と未確認箇所の検出
    ├── copy_check.py             # 文字数上限、禁止語、弱い語尾、ハッシュタグ数
    └── test_content_pack.py      # 回帰テスト
```

### 使い方

Claude Code なら `/content-pack`、Codex なら `$content-pack`。「台本を作って」「概要欄を書いて」でも作動する。

```bash
# 尺の見積りと構成チェック(目標 10 分)
python3 .agents/skills/content-pack/scripts/script_stats.py 台本.md --target 600

# ショート(フックは 2 秒以内で判定)
python3 .agents/skills/content-pack/scripts/script_stats.py 台本.md --target 45 --short

# 話者に合わせて話速を変える(既定は日本語 340 字/分、英語 150 語/分)
python3 .agents/skills/content-pack/scripts/script_stats.py 台本.md --target 600 --cpm 300

# 公開用テキストの点検(`## platform: x` の見出しで一括、または個別に指定)
python3 .agents/skills/content-pack/scripts/copy_check.py 派生物.md --platform auto
python3 .agents/skills/content-pack/scripts/copy_check.py 投稿.txt --platform x

# 回帰テスト
python3 .agents/skills/content-pack/scripts/test_content_pack.py
```

`script_stats.py` は角括弧の画面指示、HTML コメント、コードブロック、フロントマターを尺から除外し、
引用行と表の中の文字は算入する。対談台本は `--speakers 進行役,ゲスト` で行頭の話者名を除ける。

`copy_check.py` は媒体別の文字数上限、「続きを読む」前に見える範囲、ハッシュタグ数、
ハウススタイルの禁止語、言い切り型に対する弱い語尾を点検する。X は日本語を 2 単位として数える。

### 別のリポジトリで使う

このスキルは特定のリポジトリに依存しない。Second Brain 形式の保管庫で使う場合は、
その `.agent/skills/` にコピーし、保管庫のルートで実行する。

```bash
cp -r .agents/skills/content-pack /path/to/vault/.agent/skills/
cd /path/to/vault && python3 .agent/skills/content-pack/scripts/load_house_style.py
```

プロファイルが自動検出され、文体・構成テンプレート・禁止用語がそこから読み込まれる。
