# astra-riding

GPT-6 Astra が Codex 上で見せる判断様式(行動優先・完遂・質問と前提の仕分け・許可は不可逆操作のみ・変更に見合った検証・結論先出しの報告)を、
モデルに依存しない **エージェントスキル(SKILL.md)** として移植したもの。
Codex でも Claude Code でも、Astra 以外のモデルでも同じ振る舞いを引き出せる。

## 構成

```
.agents/skills/astra-riding/
├── SKILL.md                       # 核となる 8 原則と 6 ステップの判断ループ
├── agents/openai.yaml             # Codex UI 用メタデータ
├── references/
│   ├── decision-rules.md          # 許可・質問・前提・検証の詳細基準と文例
│   ├── writing-style.md           # 文体、最終回答、PR 説明のルール
│   ├── codex-setup.md             # Astra 自体の設定、effort の選び方、AGENTS.md 監査
│   ├── astra-on-sol-terra.md      # Astra を使わず Sol / Terra で Astra 並みに動かす構成
│   └── sources.md                 # 出典
├── assets/codex/                  # Sol / Terra 用: オーバーレイ、全置換指示、config.toml、hooks、検証サブエージェント
└── scripts/
    ├── audit_instructions.py      # 自律動作と衝突する記述の洗い出し
    └── install_codex.py           # assets/codex を .codex/ (または ~/.codex) と AGENTS.md に導入
.claude/skills/astra-riding -> ../../.agents/skills/astra-riding
```

## 使い方

### Codex

このリポジトリ内で作業すれば `.agents/skills/` が自動で読まれる。他のプロジェクトでも使うなら個人用ディレクトリへコピーする。

```bash
cp -r .agents/skills/astra-riding ~/.agents/skills/
```

呼び出しは `$astra-riding` を付けるか、「Astra 流で」「アストラの考え方で」と書く。作業内容が合致すれば暗黙にも適用される。

### Claude Code

`.claude/skills/astra-riding` がシンボリックリンクとして入っているので、このリポジトリでは `/astra-riding` で呼べる。
他のプロジェクトでは `~/.claude/skills/` にコピーする。

```bash
cp -rL .agents/skills/astra-riding ~/.claude/skills/
```

### Astra を使わずに Sol / Terra で動かす

```bash
python3 .agents/skills/astra-riding/scripts/install_codex.py --project   # このプロジェクトの .codex/ と AGENTS.md へ
python3 .agents/skills/astra-riding/scripts/install_codex.py --global    # ~/.codex へ
codex --profile astra-sol      # または astra-terra / astra-sol-full / astra-terra-full
```

Astra だけが持つ判断規則を Sol / Terra の組み込み指示の上に重ね、hooks でセッション開始時と圧縮後に再注入し、
最終回答前に読み取り専用の `$astra-verifier` で主張と差分を照合する。詳細は `references/astra-on-sol-terra.md`。

### 指示ファイルの監査

```bash
python3 .agents/skills/astra-riding/scripts/audit_instructions.py .
```

`AGENTS.md` / `CLAUDE.md` / `SKILL.md` から「常に確認する」「決して〜しない」のような、Astra 流の自律動作を止めやすい記述を一覧にする。
