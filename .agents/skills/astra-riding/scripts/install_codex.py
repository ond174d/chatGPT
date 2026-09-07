#!/usr/bin/env python3
"""Install the astra-riding Codex assets so GPT-5.6 Sol / Terra run with Astra's behavior rules.

使い方:
    python3 install_codex.py --project [DIR]   # <DIR>/.codex/ に導入(既定: カレント)。AGENTS.md にもオーバーレイを埋め込む
    python3 install_codex.py --global          # ~/.codex/ に導入(全プロジェクト共通)
    python3 install_codex.py --project --dry-run

何をするか:
  1. config.toml のプロファイル (astra-sol / astra-terra / *-full) を追記する。既存の config.toml は
     バックアップ(config.toml.bak-astra)を取り、astra-riding のブロックだけを置き換える。
  2. hooks.json を書く(既存があれば astra のフックだけをマージ)。
  3. hooks/astra_hook.py, agents/astra-verifier.toml, astra-instructions.md をコピーする。
  4. --project のときは AGENTS.md にマーカー付きでオーバーレイを埋め込み、.gitignore に notes ファイルを追加する。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(SKILL_DIR, "assets", "codex")
BEGIN = "# >>> astra-riding (managed block, do not edit by hand) >>>"
END = "# <<< astra-riding <<<"
MD_BEGIN = "<!-- astra-riding:overlay:start (managed, regenerate with install_codex.py) -->"
MD_END = "<!-- astra-riding:overlay:end -->"
NOTES_REL = ".codex/astra-notes.md"
GITIGNORE_ENTRIES = (NOTES_REL, ".codex/*.bak-astra")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path: str, text: str, dry: bool) -> None:
    print(f"write {path}")
    if dry:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def replace_block(existing: str, block: str, begin: str, end: str) -> str:
    if begin in existing and end in existing:
        head = existing.split(begin, 1)[0]
        tail = existing.split(end, 1)[1]
        return head + begin + "\n" + block.rstrip("\n") + "\n" + end + tail
    sep = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + begin + "\n" + block.rstrip("\n") + "\n" + end + "\n"


def render_config(codex_dir: str, hook_cmd: str) -> str:
    overlay = read(os.path.join(ASSETS, "astra-overlay.md")).strip()
    if '"""' in overlay:
        raise SystemExit("astra-overlay.md に \"\"\" が含まれているため TOML に埋め込めません")
    template = read(os.path.join(ASSETS, "config.toml"))
    instructions_path = os.path.join(codex_dir, "astra-instructions.md")
    return (
        template.replace("{{ASTRA_OVERLAY}}", overlay)
        .replace("{{ASTRA_INSTRUCTIONS_PATH}}", instructions_path)
    )


def render_hooks(existing_json: str | None, hook_cmd: str) -> str:
    template = json.loads(read(os.path.join(ASSETS, "hooks.json")))
    for event in template["hooks"].values():
        for group in event:
            for hook in group["hooks"]:
                hook["command"] = hook_cmd
    if not existing_json:
        return json.dumps(template, indent=2, ensure_ascii=False) + "\n"
    merged = json.loads(existing_json)
    merged.setdefault("hooks", {})
    for event, groups in template["hooks"].items():
        current = [g for g in merged["hooks"].get(event, []) if not _is_astra_group(g)]
        merged["hooks"][event] = current + groups
    return json.dumps(merged, indent=2, ensure_ascii=False) + "\n"


def _is_astra_group(group: dict) -> bool:
    return any("astra_hook.py" in h.get("command", "") for h in group.get("hooks", []))


def install(codex_dir: str, project_root: str | None, dry: bool) -> None:
    hook_script = os.path.join(codex_dir, "hooks", "astra_hook.py")
    hook_cmd = f"python3 {hook_script}" if project_root is None else "python3 .codex/hooks/astra_hook.py"

    # 1. config.toml
    config_path = os.path.join(codex_dir, "config.toml")
    existing = read(config_path) if os.path.exists(config_path) else ""
    if existing and not dry:
        shutil.copyfile(config_path, config_path + ".bak-astra")
        print(f"backup {config_path}.bak-astra")
    write(config_path, replace_block(existing, render_config(codex_dir, hook_cmd), BEGIN, END), dry)

    # 2. hooks.json
    hooks_path = os.path.join(codex_dir, "hooks.json")
    existing_hooks = read(hooks_path) if os.path.exists(hooks_path) else None
    write(hooks_path, render_hooks(existing_hooks, hook_cmd), dry)

    # 3. copies
    for rel in ("hooks/astra_hook.py", "agents/astra-verifier.toml", "astra-instructions.md"):
        write(os.path.join(codex_dir, rel), read(os.path.join(ASSETS, rel)), dry)
    if not dry:
        os.chmod(hook_script, 0o755)

    # 4. project extras
    if project_root is not None:
        agents_md = os.path.join(project_root, "AGENTS.md")
        overlay = read(os.path.join(ASSETS, "astra-overlay.md")).strip()
        current = read(agents_md) if os.path.exists(agents_md) else ""
        write(agents_md, replace_block(current, overlay, MD_BEGIN, MD_END), dry)
        gitignore = os.path.join(project_root, ".gitignore")
        gi = read(gitignore) if os.path.exists(gitignore) else ""
        missing = [e for e in GITIGNORE_ENTRIES if e not in gi.splitlines()]
        if missing:
            write(gitignore, gi + ("" if not gi or gi.endswith("\n") else "\n") + "\n".join(missing) + "\n", dry)

    print("\n次の一手:")
    print("  codex --profile astra-sol      # または astra-terra / astra-sol-full / astra-terra-full")
    print("  export CODEX_PROFILE=astra-sol # 常時有効にする場合")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--project", nargs="?", const=".", metavar="DIR", help="<DIR>/.codex に導入")
    mode.add_argument("--global", dest="global_", action="store_true", help="~/.codex に導入")
    parser.add_argument("--dry-run", action="store_true", help="書き込まずに予定を表示")
    args = parser.parse_args(argv[1:])

    if args.global_:
        codex_dir = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
        install(codex_dir, None, args.dry_run)
    else:
        root = os.path.abspath(args.project)
        install(os.path.join(root, ".codex"), root, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
