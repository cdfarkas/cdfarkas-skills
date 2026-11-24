#!/usr/bin/env python3
"""Check every skills/*/SKILL.md against the Agent Skills specification, and the marketplace hooks.

Rules enforced (https://agentskills.io/specification):
  - frontmatter exists and carries `name` and `description`
  - `name` is kebab-case, at most 64 chars, and equals the parent directory name
  - `description` is at most 1024 characters
  - the body stays under 500 lines, so it does not swamp the context when loaded
  - every referenced local file exists
  - a script under scripts/ that pushes, edits a PR or calls a write endpoint takes --dry-run
  - a marketplace entry's `hooks` is an inline object mapping event names to arrays, and every
    ${CLAUDE_PLUGIN_ROOT}/... script named in it exists
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MANIFEST = Path(".claude-plugin/marketplace.json")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_BODY_LINES = 500
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MUTATING_RE = re.compile(r"git push|gh pr (create|edit|merge|close)|gh api .*(-X|--method) (POST|PATCH|PUT|DELETE)")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block, out, key = text[3:end], {}, None
    for line in block.splitlines():
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            out[key] = m.group(2).strip().lstrip(">").strip()
        elif key and line.startswith("  "):
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def check(path: Path) -> list[str]:
    text = path.read_text()
    errors: list[str] = []
    fm = parse_frontmatter(text)

    if not fm:
        return [f"{path}: no YAML frontmatter"]

    name = fm.get("name")
    if not name:
        errors.append(f"{path}: frontmatter has no `name`")
    else:
        if not NAME_RE.match(name):
            errors.append(f"{path}: name '{name}' is not kebab-case")
        if len(name) > MAX_NAME:
            errors.append(f"{path}: name is {len(name)} chars, max {MAX_NAME}")
        if name != path.parent.name:
            errors.append(f"{path}: name '{name}' must equal the directory '{path.parent.name}'")

    description = fm.get("description")
    if not description:
        errors.append(f"{path}: frontmatter has no `description`")
    elif len(description) > MAX_DESCRIPTION:
        errors.append(f"{path}: description is {len(description)} chars, max {MAX_DESCRIPTION}")

    body = text[text.find("\n---", 3) + 4:]
    if len(body.splitlines()) > MAX_BODY_LINES:
        errors.append(f"{path}: body is {len(body.splitlines())} lines, keep it under {MAX_BODY_LINES}")

    for ref in re.findall(r"\]\(([^)h][^)]*\.md)\)", body) + re.findall(r"`([a-z0-9_/.-]+\.(?:md|sh|jq|py|json))`", body):
        if "<" in ref or ref.startswith("/"):
            continue
        if not (path.parent / ref).exists():
            errors.append(f"{path}: references '{ref}', which does not exist")

    for script in sorted(path.parent.glob("scripts/*.sh")):
        code = script.read_text()
        if MUTATING_RE.search(code) and "--dry-run" not in code:
            errors.append(f"{script}: changes state (push / PR write / write API) but takes no --dry-run")

    return errors


def check_hooks(manifest: Path) -> list[str]:
    errors: list[str] = []
    for plugin in json.loads(manifest.read_text())["plugins"]:
        if "hooks" not in plugin:
            continue
        where, hooks = f"{manifest}: {plugin['name']}", plugin["hooks"]
        if not isinstance(hooks, dict):
            errors.append(f"{where}: `hooks` must be an inline object, not {json.dumps(hooks)}")
            continue
        for event, groups in hooks.items():
            if not isinstance(groups, list):
                errors.append(f"{where}: `hooks.{event}` must be an array")
            for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)", json.dumps(groups)):
                if not (Path(plugin["source"]) / ref).is_file():
                    errors.append(f"{where}: `hooks.{event}` runs '{ref}', which does not exist")
    return errors


def main() -> int:
    skills = sorted(Path("skills").glob("*/SKILL.md"))
    if not skills:
        print("no skills found under skills/*/SKILL.md")
        return 1

    all_errors = [e for s in skills for e in check(s)] + check_hooks(MANIFEST)
    if all_errors:
        print(f"Found {len(all_errors)} problem(s):\n")
        for e in all_errors:
            print(f"  ✗ {e}")
        return 1

    print(f"✓ {len(skills)} skill(s) valid "
          f"(name matches directory, description ≤ {MAX_DESCRIPTION} chars, body < {MAX_BODY_LINES} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
