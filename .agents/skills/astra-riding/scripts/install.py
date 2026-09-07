#!/usr/bin/env python3
"""Install the astra-riding operating discipline into an agent environment.

使い方:
    python3 install.py --project [DIR]              # 使っているエージェントを自動判別して導入
    python3 install.py --project --target claude    # 対象を指定 (claude | codex | agents-md | all)
    python3 install.py --global --target all --with-skill
    python3 install.py --project --dry-run

対象ごとに何を書くか:

  agents-md  <root>/AGENTS.md に管理ブロックとしてオーバーレイを埋め込む。
             AGENTS.md を読むエージェント全般(Codex, Cursor, Gemini CLI, Copilot ほか)に効く。

  claude     CLAUDE.md に管理ブロック、.claude/agents/astra-verifier.md、
             .claude/hooks/rulecard_hook.py、.claude/settings.json の hooks をマージ。

  codex      .codex/config.toml にプロファイル (astra-sol / astra-terra / *-full)、
             .codex/hooks.json、.codex/hooks/rulecard_hook.py、.codex/agents/astra-verifier.toml、
             .codex/astra-instructions.md。AGENTS.md も併せて更新する。

いずれも管理ブロック方式なので、再実行すれば中身が更新され、手書き部分は残る。
既存ファイルはバックアップ (*.bak-astra) を取る。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(SKILL_DIR, "assets")
SKILL_NAME = os.path.basename(SKILL_DIR)

TOML_BEGIN = "# >>> astra-riding (managed block, do not edit by hand) >>>"
TOML_END = "# <<< astra-riding <<<"
MD_BEGIN = "<!-- astra-riding:overlay:start (managed, regenerate with install.py) -->"
MD_END = "<!-- astra-riding:overlay:end -->"

NOTES_FILE = ".astra-notes.md"
GITIGNORE_ENTRIES = (NOTES_FILE, "*.bak-astra")

TARGETS = ("claude", "codex", "agents-md")


# --- file helpers -----------------------------------------------------------

def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def asset(*parts: str) -> str:
    return read(os.path.join(ASSETS, *parts))


def write(path: str, text: str, dry: bool, executable: bool = False) -> None:
    print(f"  write {path}")
    if dry:
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if executable:
        os.chmod(path, 0o755)


def backup(path: str, dry: bool) -> None:
    if os.path.exists(path) and not dry:
        shutil.copyfile(path, path + ".bak-astra")
        print(f"  backup {path}.bak-astra")


def replace_block(existing: str, block: str, begin: str, end: str) -> str:
    """管理ブロックを差し替える。無ければ末尾に追記する。"""
    if begin in existing and end in existing:
        head = existing.split(begin, 1)[0]
        tail = existing.split(end, 1)[1]
        return head + begin + "\n" + block.rstrip("\n") + "\n" + end + tail
    if not existing:
        sep = ""
    elif existing.endswith("\n\n"):
        sep = ""
    elif existing.endswith("\n"):
        sep = "\n"
    else:
        sep = "\n\n"
    return existing + sep + begin + "\n" + block.rstrip("\n") + "\n" + end + "\n"


def write_managed_md(path: str, dry: bool) -> None:
    existing = read(path) if os.path.exists(path) else ""
    overlay = asset("overlay.md").strip()
    updated = replace_block(existing, overlay, MD_BEGIN, MD_END)
    if updated == existing:
        print(f"  unchanged {path}")
        return
    backup(path, dry)
    write(path, updated, dry)


def hook_command(hooks_dir: str, root: str | None) -> str:
    """プロジェクト導入では相対パスにして、チェックアウト先が変わっても動くようにする。"""
    script = os.path.join(hooks_dir, "rulecard_hook.py")
    if root is not None:
        script = os.path.relpath(script, root)
    return f"python3 {script}"


def install_hook_files(hooks_dir: str, dry: bool) -> None:
    write(os.path.join(hooks_dir, "rulecard_hook.py"), asset("hooks", "rulecard_hook.py"), dry, executable=True)
    write(os.path.join(hooks_dir, "rulecard.md"), asset("rulecard.md"), dry)
    stale = os.path.join(hooks_dir, "astra_hook.py")
    if os.path.exists(stale):
        print(f"  remove {stale} (旧バージョンの残り)")
        if not dry:
            os.remove(stale)


HOOK_MARKERS = ("rulecard_hook.py", "astra_hook.py")


def merge_json_hooks(path: str, addition: dict, dry: bool) -> None:
    """既存の hooks 設定を保ったまま、astra-riding のフックだけを差し替える。"""
    current: dict = {}
    if os.path.exists(path):
        try:
            current = json.loads(read(path) or "{}")
        except json.JSONDecodeError:
            print(f"  skip {path}: JSON として読めないため手動でマージしてください")
            return
        backup(path, dry)
    if not isinstance(current, dict):
        print(f"  skip {path}: オブジェクトではないため手動でマージしてください")
        return
    hooks = current.setdefault("hooks", {})
    for event, groups in addition["hooks"].items():
        kept = [g for g in hooks.get(event, []) if not _is_ours(g)]
        hooks[event] = kept + groups
    write(path, json.dumps(current, indent=2, ensure_ascii=False) + "\n", dry)


def _is_ours(group: dict) -> bool:
    """astra-riding が過去に書いたフック群かどうか(旧いスクリプト名も拾う)。"""
    if not isinstance(group, dict):
        return False
    commands = [str(h.get("command", "")) for h in group.get("hooks", []) if isinstance(h, dict)]
    return any(marker in command for command in commands for marker in HOOK_MARKERS)


# --- targets ----------------------------------------------------------------

def install_agents_md(root: str | None, dry: bool) -> None:
    """リポジトリ直下の AGENTS.md。--global では Codex が読むユーザー全体の AGENTS.md。"""
    print("[agents-md]")
    if root is not None:
        target = os.path.join(root, "AGENTS.md")
    else:
        home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
        target = os.path.join(home, "AGENTS.md")
    write_managed_md(target, dry)


def install_claude(base: str, root: str | None, dry: bool) -> None:
    print("[claude]")
    claude_dir = os.path.join(base, ".claude") if root is not None else base
    md_path = os.path.join(root if root is not None else base, "CLAUDE.md")
    write_managed_md(md_path, dry)
    write(os.path.join(claude_dir, "agents", "astra-verifier.md"), asset("claude", "agents", "astra-verifier.md"), dry)
    hooks_dir = os.path.join(claude_dir, "hooks")
    install_hook_files(hooks_dir, dry)
    template = json.loads(asset("claude", "settings-hooks.json"))
    command = hook_command(hooks_dir, root)
    for groups in template["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                hook["command"] = command
    merge_json_hooks(os.path.join(claude_dir, "settings.json"), template, dry)


def install_codex(base: str, root: str | None, dry: bool) -> None:
    print("[codex]")
    codex_dir = os.path.join(base, ".codex") if root is not None else base
    if root is not None:
        write_managed_md(os.path.join(root, "AGENTS.md"), dry)

    hooks_dir = os.path.join(codex_dir, "hooks")
    install_hook_files(hooks_dir, dry)
    write(os.path.join(codex_dir, "agents", "astra-verifier.toml"), asset("codex", "agents", "astra-verifier.toml"), dry)
    write(os.path.join(codex_dir, "astra-instructions.md"), asset("codex", "astra-instructions.md"), dry)

    template = json.loads(asset("codex", "hooks.json"))
    command = hook_command(hooks_dir, root)
    for groups in template["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                hook["command"] = command
    merge_json_hooks(os.path.join(codex_dir, "hooks.json"), template, dry)

    overlay = asset("overlay.md").strip()
    if '"""' in overlay:
        raise SystemExit('assets/overlay.md に """ が含まれているため TOML に埋め込めません')
    config_block = (
        asset("codex", "config.toml")
        .replace("{{OVERLAY}}", overlay)
        .replace("{{INSTRUCTIONS_PATH}}", os.path.join(codex_dir, "astra-instructions.md"))
    )
    config_path = os.path.join(codex_dir, "config.toml")
    existing = read(config_path) if os.path.exists(config_path) else ""
    backup(config_path, dry)
    write(config_path, replace_block(existing, config_block, TOML_BEGIN, TOML_END), dry)


def install_skill_copy(base: str, root: str | None, dry: bool) -> None:
    """スキル本体を、そのエージェントが読むスキルディレクトリに置く。"""
    print("[skill]")
    if root is not None:
        dests = [os.path.join(root, ".claude", "skills", SKILL_NAME), os.path.join(root, ".agents", "skills", SKILL_NAME)]
    else:
        home = os.path.expanduser("~")
        dests = [os.path.join(home, ".claude", "skills", SKILL_NAME), os.path.join(home, ".agents", "skills", SKILL_NAME)]
    for dest in dests:
        if os.path.realpath(dest) == os.path.realpath(SKILL_DIR):
            print(f"  skip {dest} (元の場所)")
            continue
        print(f"  copy  {dest}")
        if dry:
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.islink(dest):
            os.unlink(dest)
        elif os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(SKILL_DIR, dest, symlinks=False)


def update_gitignore(root: str, dry: bool) -> None:
    path = os.path.join(root, ".gitignore")
    current = read(path) if os.path.exists(path) else ""
    missing = [e for e in GITIGNORE_ENTRIES if e not in current.splitlines()]
    if not missing:
        return
    sep = "" if not current or current.endswith("\n") else "\n"
    write(path, current + sep + "\n".join(missing) + "\n", dry)


# --- detection and entry point ---------------------------------------------

def detect(root: str) -> list[str]:
    found = []
    if os.path.exists(os.path.join(root, ".claude")) or os.path.exists(os.path.join(root, "CLAUDE.md")):
        found.append("claude")
    if os.path.exists(os.path.join(root, ".codex")):
        found.append("codex")
    if "codex" not in found:
        found.append("agents-md")
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--project", nargs="?", const=".", metavar="DIR", help="プロジェクトに導入(既定: カレント)")
    mode.add_argument("--global", dest="global_", action="store_true", help="ユーザー全体に導入 (~/.claude, ~/.codex)")
    parser.add_argument(
        "--target", default="auto", choices=("auto", "all", *TARGETS),
        help="導入先。auto は既存ファイルから判別、all は全部",
    )
    parser.add_argument("--with-skill", action="store_true", help="スキル本体もスキルディレクトリへコピーする")
    parser.add_argument("--dry-run", action="store_true", help="書き込まずに予定を表示")
    args = parser.parse_args(argv[1:])

    dry = args.dry_run
    root = None if args.global_ else os.path.abspath(args.project)

    if args.target == "auto":
        targets = detect(root) if root else ["claude", "codex"]
    elif args.target == "all":
        targets = list(TARGETS)
    else:
        targets = [args.target]
    print(f"targets: {', '.join(targets)}\n")

    home = os.path.expanduser("~")
    for target in targets:
        if target == "agents-md":
            install_agents_md(root, dry)
        elif target == "claude":
            install_claude(root if root else os.path.join(home, ".claude"), root, dry)
        elif target == "codex":
            base = root if root else (os.environ.get("CODEX_HOME") or os.path.join(home, ".codex"))
            install_codex(base, root, dry)

    if args.with_skill:
        install_skill_copy(root if root else home, root, dry)
    if root:
        update_gitignore(root, dry)

    print("\n次の一手:")
    if "codex" in targets:
        print("  codex --profile astra-sol        # または astra-terra / astra-sol-full / astra-terra-full")
    if "claude" in targets:
        print("  claude                           # CLAUDE.md と hooks が次のセッションから効く")
    print("  python3 %s/scripts/audit_instructions.py ." % SKILL_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
