#!/usr/bin/env python3
"""Preflight/apply the scoped Android 11 patches, without resets or git am."""
import argparse
from pathlib import Path
import subprocess
import sys


DEVICE = Path(__file__).resolve().parents[1]
PATCHES = DEVICE / "patches/android-11"
COMPONENTS = ("hardware/interfaces", "system/bt", "system/media", "system/core")


def run(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "apply", *args],
                          capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="preflight only (default)")
    mode.add_argument("--apply", action="store_true", help="apply after all checks pass")
    args = parser.parse_args()
    pending = []
    failures = []
    for component in COMPONENTS:
        repo = (args.source_root / component).resolve()
        # A parent Git checkout would silently skip these component-relative
        # paths. Require the actual component root before checking either way.
        root = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True)
        if root.returncode or Path(root.stdout.strip()).resolve() != repo:
            failures.append(f"not a component Git root: {repo}")
            continue
        for patch in sorted((PATCHES / component).glob("*.patch")):
            patch = patch.resolve()
            if not repo.is_dir():
                failures.append(f"missing source directory: {repo}")
                continue
            if run(repo, "--reverse", "--check", str(patch)).returncode == 0:
                print(f"Already applied: {component}/{patch.name}")
                continue
            check = run(repo, "--check", str(patch))
            if check.returncode:
                failures.append(f"{component}/{patch.name}: {check.stderr.strip()}")
            else:
                print(f"Ready: {component}/{patch.name}")
                pending.append((repo, patch))
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    if not args.apply:
        print("Preflight passed. No source files changed.")
        return 0
    applied = []
    for repo, patch in pending:
        result = run(repo, str(patch))
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            # Reverse only patches applied by this invocation, preserving user work.
            for old_repo, old_patch in reversed(applied):
                undo = run(old_repo, "--reverse", str(old_patch))
                if undo.returncode:
                    print(f"Rollback needs attention: {old_patch}\n{undo.stderr}",
                          file=sys.stderr)
            return 1
        applied.append((repo, patch))
        print(f"Applied: {patch.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
