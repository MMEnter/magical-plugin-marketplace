#!/usr/bin/env python3
"""protect-eval: ask for confirmation before editing the files an eval depends on.

PreToolUse hook for Edit, Write, MultiEdit and NotebookEdit. Reads the tool call as JSON on stdin.
If the target file matches a protected pattern, prints a permission decision of "ask" so the user
sees a prompt; otherwise prints nothing and exits 0 (normal permission flow).

It fails open: any error (bad input, unreadable config) logs to stderr and exits 0, so a bug here can
never block work. Standard library only.

Protected patterns
  * built-in defaults (DEFAULT_PATTERNS below);
  * project additions, one glob per line, in ``.eval-protected`` at the project root
    (``#`` starts a comment);
  * a line starting with ``!`` removes a default for that project, e.g. ``!**/*judge*``.

Pattern syntax (matched against the path relative to the project root, with forward slashes):
  ``*`` matches within one path segment; ``**/`` matches any number of directories; ``**`` matches
  anything. A pattern also matches everything beneath a directory it matches, as in .gitignore.
  Matching is case-insensitive on Windows.
"""

import json
import os
import re
import sys

DEFAULT_PATTERNS = [
    "**/*grader*",
    "**/*judge*",
    "**/gold*",
    "**/*holdout*",
    "**/tasks*.jsonl",
    "**/eval_results/**",
    "**/runs.jsonl",
    "**/.eval-protected",  # so the opt-outs can't be added silently
]

CONFIG_NAME = ".eval-protected"

REASON = ("This file is part of the eval (graders, gold data or scoring). Changing it changes the "
          "measurement, not the system. Confirm only if the grader itself is wrong.")

PATH_FIELDS = ("file_path", "notebook_path", "path")


def _log(message):
    print(f"protect_eval: {message}", file=sys.stderr)


def glob_to_regex(pattern):
    """Translate a glob to a regex; ``*`` stays inside a segment, ``**/`` spans directories."""
    i, out = 0, []
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def read_config(project_root):
    """Return (added_patterns, removed_patterns) from .eval-protected; empty if absent or unreadable."""
    added, removed = [], []
    path = os.path.join(project_root, CONFIG_NAME)
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("!"):
                    removed.append(line[1:].strip())
                else:
                    added.append(line)
    except FileNotFoundError:
        pass
    except OSError as exc:
        _log(f"could not read {path}: {exc}")
    return added, removed


def active_patterns(project_root):
    added, removed = read_config(project_root)
    return [p for p in DEFAULT_PATTERNS if p not in removed] + added


def normalise(target, cwd, project_root):
    """Absolute, forward-slash path; relative to the project root when it is inside it."""
    target = os.path.expanduser(target)
    if not os.path.isabs(target):
        target = os.path.join(cwd, target)
    target = os.path.normpath(target)
    root = os.path.normpath(project_root)
    try:
        inside = os.path.commonpath([os.path.normcase(target), os.path.normcase(root)]) == os.path.normcase(root)
    except ValueError:  # different drives on Windows
        inside = False
    rel = os.path.relpath(target, root) if inside else target
    return rel.replace("\\", "/").lstrip("/")


def matches(rel_path, patterns, case_insensitive=None):
    """True if the path, or any directory above it, matches one of the patterns."""
    if case_insensitive is None:
        case_insensitive = os.name == "nt"
    flags = re.IGNORECASE if case_insensitive else 0
    parts = [p for p in rel_path.split("/") if p]
    candidates = ["/".join(parts[: n + 1]) for n in range(len(parts))]
    for pattern in patterns:
        regex = re.compile("^" + glob_to_regex(pattern.replace("\\", "/")) + "$", flags)
        if any(regex.match(c) for c in candidates):
            return pattern
    return None


def decide(payload, project_root=None):
    """Return the hook output dict for a protected path, or None for the normal flow."""
    tool_input = payload.get("tool_input") or {}
    target = next((tool_input[f] for f in PATH_FIELDS if isinstance(tool_input.get(f), str)), None)
    if not target:
        return None
    cwd = payload.get("cwd") or os.getcwd()
    root = project_root or os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    rel = normalise(target, cwd, root)
    hit = matches(rel, active_patterns(root))
    if not hit:
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": f"{REASON} (matched {hit!r})",
    }}


def main():
    try:
        payload = json.load(sys.stdin)
        result = decide(payload)
        if result:
            print(json.dumps(result))
    except Exception as exc:  # noqa: BLE001 - fail open
        _log(f"ignored error: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
