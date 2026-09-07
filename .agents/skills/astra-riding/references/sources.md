# 出典

このスキルの内容は次の公開情報にもとづく(2026 年 9 月 7 日時点)。

## 一次情報(OpenAI)

- GPT-6 Astra 発表: https://openai.com/index/gpt-6-astra/
- Path to Astra(能力とセーフガード): https://openai.com/index/path-to-astra/
- GPT-6 Astra System Card: https://deploymentsafety.openai.com/gpt-6-astra
- API モデルページ: https://developers.openai.com/api/docs/models/gpt-6-astra
- Codex スキルの作り方: https://developers.openai.com/codex/skills
- openai/skills の skill-creator(SKILL.md / openai.yaml 仕様): https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md

## Codex 上で GPT-6 Astra に与えられているシステムプロンプト(公開転載)

- https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/Codex/gpt-6-astra.md

SKILL.md の原則(行動優先、完遂、許可の基準、質問と前提の扱い、検証の比例、文体)は
主にこの文書の内容を手順として言い換えたもの。

## Sol / Terra との比較に使った資料

- Codex 上の GPT-5.6(Sol)システムプロンプト(公開転載): https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/Codex/gpt-5.6.md
- GPT-5.6 Sol / Terra / Luna の発表: https://openai.com/index/gpt-5-6/
- GPT-5.6 Terra モデルページ: https://developers.openai.com/api/docs/models/gpt-5.6-terra
- Sol の実運用での不満(指示の読み飛ばし、回り道): https://github.com/openai/codex/issues/36538
- Astra と Sol の挙動差(質問、舵取り、正直さ、トークン効率): https://codersera.com/blog/gpt-6-astra-vs-gpt-5-6-sol-2026/ 、 https://ustechautomations.com/resources/blog/gpt-6-astra-vs-5-sol-for-codex-token-efficiency-2026
- Codex の設定階層(model_instructions_file > AGENTS.md > ユーザー): https://github.com/Austin1serb/agents-md/blob/main/change-codex-system-prompt.md
- developer_instructions が Codex App で付かない報告: https://github.com/openai/codex/issues/11004
- Codex hooks の形式とイベント: https://github.com/shanraisshan/codex-cli-best-practice/blob/main/best-practice/codex-hooks.md 、 https://developers.openai.com/codex/hooks
- Codex カスタムサブエージェントの TOML 形式: https://developers.openai.com/codex/subagents 、 https://github.com/proflead/codex-agents-library
- Sol の ultra モードと effort: https://codex.danielvaughan.com/2026/06/26/gpt-5-6-sol-terra-luna-preview-codex-cli-model-tiers-pricing-ultra-mode-configuration/

## 二次情報

- Codex CLI での Astra 設定: https://codex.danielvaughan.com/2026/09/03/gpt-6-astra-codex-cli-configuration-context-notes-safety/
- Astra 切り替え時の 4 項目(履歴管理・指示・推論強度・速度): https://smartscope.blog/blog/codex-astra-four-settings-2026/
- reasoning effort とコスト: https://paddo.dev/blog/gpt-6-astra-critical-generally-available
- Astra の思考レベル解説: https://fyve.co.jp/codex/articles/gpt-6-astra-effort-max
- Codex スキルの保存場所と優先順位: https://knightli.com/en/2026/04/29/difference-between-global-and-project-codex-skills/
