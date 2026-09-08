# どのエージェントにも常時適用する

スキルとして毎回呼び出す代わりに、指示ファイル・hooks・検証サブエージェントとして環境に埋め込む方法。
`scripts/install.py` が対象を判別して書き込む。すべて**管理ブロック方式**なので、再実行すれば
中身だけが更新され、手書きした部分は残る。既存ファイルはバックアップ(`*.bak-astra`)を取る。

## 目次

1. 何がどこに入るか
2. 導入コマンド
3. 対象別の詳細(Claude Code / Codex / AGENTS.md 系)
4. 4 層モデル
5. 導入後の確認
6. 外し方

## 1. 何がどこに入るか

| 素材 | 役割 | 入る場所 |
| --- | --- | --- |
| `assets/overlay.md` | 判断規則の本体。指示ファイルに埋め込む | CLAUDE.md、AGENTS.md、Codex の `developer_instructions` |
| `assets/rulecard.md` | 11 行に圧縮した規則カード | hooks が注入する |
| `assets/hooks/rulecard_hook.py` | セッション開始時と圧縮後にカードとノートを注入 | `.claude/hooks/`、`.codex/hooks/` |
| `assets/claude/agents/astra-verifier.md` | 引き渡し前の検証サブエージェント(Claude Code 形式) | `.claude/agents/` |
| `assets/codex/agents/astra-verifier.toml` | 同(Codex 形式) | `.codex/agents/` |
| `assets/codex/config.toml` | Sol / Terra 用プロファイル | `.codex/config.toml` |
| `assets/codex/astra-instructions.md` | 組み込み指示を全置換する版 | `.codex/astra-instructions.md` |

## 2. 導入コマンド

```bash
# 使っているエージェントを自動判別して、このプロジェクトに導入
python3 .agents/skills/astra-riding/scripts/install.py --project

# 対象を指定する (claude | codex | agents-md | all)
python3 .agents/skills/astra-riding/scripts/install.py --project --target all

# ユーザー全体に導入し、スキル本体も ~/.claude/skills と ~/.agents/skills へコピー
python3 .agents/skills/astra-riding/scripts/install.py --global --target all --with-skill

# 書き込まずに予定だけ見る
python3 .agents/skills/astra-riding/scripts/install.py --project --dry-run
```
> Windows では `python3` を `py -3`(ランチャーが無ければ `python`)に読み替える。
> `install.py` は自動で判定し、`--python` で明示指定もできる。


自動判別は、`.claude/` か `CLAUDE.md` があれば claude、`.codex/` があれば codex、
それ以外は agents-md を選ぶ。`--global` では claude と codex の両方に入れる。

`--target skill` はスキル本体のコピーだけを行い、指示ファイルや hooks には触れない。
既に独自の運用ルールを持つ保管庫やリポジトリに、スキルだけを足したいときに使う。
`--skills all` で隣接するスキルをまとめて、`--skills-dir` でコピー先を明示できる。
コピー先を省略しても、`<root>/.agent/skills` があれば自動的に対象に加わる。

```bash
python3 .agents/skills/astra-riding/scripts/install.py \
  --project /path/to/vault --target skill --skills all \
  --skills-dir /path/to/vault/.agent/skills
```

`--global --target agents-md` は、Codex がユーザー全体の指示として読む `~/.codex/AGENTS.md` に書く。
ホーム直下の `AGENTS.md` を読むエージェントは一般的ではないため、そこには書かない。

## 3. 対象別の詳細

### Claude Code

- `CLAUDE.md` に管理ブロックでオーバーレイを埋め込む。プロジェクト直下(`--project`)か `~/.claude/CLAUDE.md`(`--global`)。
- `.claude/agents/astra-verifier.md` に読み取り専用の検証サブエージェントを置く。引き渡し前に呼び出すと、依頼との突き合わせと主張の裏づけを確認する。
- `.claude/hooks/rulecard_hook.py` を置き、`.claude/settings.json` の `SessionStart`(matcher: `startup|resume|clear|compact`)と `PreCompact` に登録する。既存の hooks 設定は保たれ、astra-riding のエントリだけが差し替わる。
- プロジェクト導入ではフックのコマンドを相対パスで書くので、別のマシンにチェックアウトしても動く。

### Codex

- `AGENTS.md` に管理ブロックでオーバーレイを埋め込む。
- `.codex/config.toml` に `astra-sol` / `astra-terra` と、組み込み指示を全置換する `astra-sol-full` / `astra-terra-full` を追加する。起動は `codex --profile astra-sol` または `CODEX_PROFILE=astra-sol`。
- `.codex/hooks.json` に `SessionStart` と `PostCompact` を登録し、`.codex/hooks/rulecard_hook.py` を置く。
- `.codex/agents/astra-verifier.toml` に検証サブエージェントを置く。Codex はカスタムサブエージェントを自動起動しないので、プロンプトで明示的に委譲する。
- モデル別の推奨設定は [codex-setup.md](codex-setup.md) と [astra-on-sol-terra.md](astra-on-sol-terra.md)。

### AGENTS.md を読むエージェント全般

Cursor、Gemini CLI、GitHub Copilot、その他 AGENTS.md 規約に対応したツールは、
`--target agents-md` でリポジトリ直下の `AGENTS.md` にオーバーレイが入るだけで効く。
対応状況はツールとバージョンで変わるので、導入後に実際の挙動で確かめる。
各ツール固有の指示ファイル(`.cursorrules`、`.cursor/rules/*.mdc`、`GEMINI.md`、
`.github/copilot-instructions.md`)を使っている場合は、`assets/overlay.md` の内容を
そのファイルへ手で貼るか、管理ブロックのマーカーごとコピーする。

hooks とサブエージェントに相当する仕組みが無いツールでは、1 層目(指示)だけが効く。
その場合は長い作業でノートファイル(既定 `.astra-notes.md`)を自分で維持し、
文脈が切れたら読み直すよう依頼文に一言入れると、圧縮後の脱線をかなり防げる。

## 4. 4 層モデル

| 層 | 効果 | 無いとどうなるか |
| --- | --- | --- |
| 1. 指示(オーバーレイ) | 判断規則そのもの | 何も始まらない。最低限これだけは入れる |
| 2. 設定(プロファイル・推論強度) | 規則を守る余力を確保する | 規則はあるが、難しい局面で守り切れない |
| 3. hooks(再注入) | セッション開始時と圧縮後に規則を思い出させる | 長い作業の後半で規則が薄れ、目的を見失う |
| 4. 検証サブエージェント | 引き渡し前に主張と成果物を突き合わせる | 「やった」と言うが根拠がない報告が残る |

上から順に効果が大きく、下ほど補助的。まず 1 層目、長い作業が多いなら 3 層目、
成果物の正確さが重要なら 4 層目を足す。

## 5. 導入後の確認

```bash
# 既存の指示ファイルに、この原則と衝突する記述が残っていないか調べる
python3 .agents/skills/astra-riding/scripts/audit_instructions.py .

# フックが期待どおりの文面を出すか確認する
echo '{"hook_event_name":"SessionStart","source":"compact"}' | python3 .claude/hooks/rulecard_hook.py
```

監査スクリプトは AGENTS.md / CLAUDE.md / GEMINI.md / SKILL.md / `.cursorrules` /
`.cursor/rules/*.mdc` / `.github/copilot-instructions.md` などを走査し、
「常に確認する」「決して〜しない」型の記述を一覧にする。管理ブロックの中身は対象外。
挙がった行は「取り消せない操作を守るために今も必要か」で判断し、不要なら削除、
必要なら何が不可逆なのかを添えて書き直す。

## 6. 外し方

管理ブロック(`<!-- astra-riding:overlay:start -->` 〜 `end`、TOML は `# >>> astra-riding` 〜 `# <<<`)を
ファイルごと削除するか、バックアップ(`*.bak-astra`)に戻す。
hooks は `settings.json` / `hooks.json` から `rulecard_hook.py` を参照するエントリを消す。
