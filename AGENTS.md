# AGENTS.md

このリポジトリは Codex / Claude Code 向けのスキル置き場。

- 実装・修正・調査などの作業は `.agents/skills/astra-riding/SKILL.md` の判断ループに従って進める。
- スキルを編集したら `python3 .agents/skills/astra-riding/scripts/audit_instructions.py .` を実行し、Astra 流の自律動作と衝突する記述が増えていないか確認する。
- `.claude/skills/astra-riding` は `.agents/skills/astra-riding` へのシンボリックリンク。実体は `.agents` 側だけを編集する。
