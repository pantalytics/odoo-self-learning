#!/usr/bin/env python3
"""Fail when an Odoo module changes without a higher manifest version.

CloudPepper (auto_upgrade) and Odoo.sh (production) only run ``-u <module>``
when the version in ``__manifest__.py`` is higher than the version installed
in the database. Ship new fields with the same version and the code goes live
on the old schema: ``column ... does not exist``, and nothing works until
someone upgrades by hand.

Rule: every change to a module's code or data needs a higher version than the
target branch has. Docs, tests and static assets are exempt.

    tools/check_manifest_version.py                 # against origin/<default branch>
    tools/check_manifest_version.py origin/19.0     # against a given ref

Standalone, stdlib only, no Odoo needed. Exit 1 lists every module to bump.
Canonical copy: pantalytics/odoo-self-learning, tools/check_manifest_version.py.
Copy it unchanged into other repos.
"""

import ast
import os
import subprocess
import sys
from pathlib import PurePosixPath

# Paths inside a module whose change does not need an upgrade. Static files
# (JS, CSS, images) are served from disk and the asset bundles rebuild from
# their checksums, so they go live without -u.
EXEMPT_DIRS = {"tests", "static", "doc", "docs", "readme"}
EXEMPT_SUFFIXES = {".md", ".rst", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".svg"}
# Module folders that are fixtures, not shipped addons.
SKIP_MODULE_PARTS = {"setup", "ci_addons", "node_modules", ".git"}


def git(*args, check=True):
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and result.returncode:
        sys.exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def default_base():
    if os.environ.get("GITHUB_BASE_REF"):
        return f"origin/{os.environ['GITHUB_BASE_REF']}"
    head = git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    if head.returncode == 0:
        return head.stdout.strip().removeprefix("refs/remotes/")
    sys.exit("No base ref given and origin/HEAD is not set. Pass one, e.g. origin/19.0.")


def version_of(manifest_source):
    try:
        manifest = ast.literal_eval(manifest_source)
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"manifest is not a plain dict literal ({exc})") from exc
    raw = str(manifest.get("version", "")).strip()
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        raise ValueError(f"version {raw!r} is not dotted integers, e.g. 19.0.1.0.0") from None


def is_newer(new, old):
    """Compare like Odoo does: a 19.0 branch at 19.0.2.0.0 and an 18.0
    branch cut from it at 18.0.2.0.0 are the same release, so when the series
    differ only the module part counts."""
    if len(new) == len(old) == 5 and new[:2] != old[:2]:
        return new[2:] > old[2:]
    return new > old


def exempt(path_in_module):
    parts = PurePosixPath(path_in_module).parts
    if any(part in EXEMPT_DIRS for part in parts[:-1]):
        return True
    name = parts[-1]
    return PurePosixPath(name).suffix.lower() in EXEMPT_SUFFIXES or name.lower().startswith("readme")


def modules_in_worktree():
    tracked = git("ls-files", "*__manifest__.py", "__manifest__.py").stdout.split()
    modules = []
    for manifest in tracked:
        module = str(PurePosixPath(manifest).parent)
        if not SKIP_MODULE_PARTS & set(PurePosixPath(module).parts):
            modules.append(module)
    return modules


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else default_base()
    os.chdir(git("rev-parse", "--show-toplevel").stdout.strip())

    merge_base = git("merge-base", base, "HEAD", check=False)
    if merge_base.returncode:
        sys.exit(f"No merge base between {base} and HEAD; fetch more history (fetch-depth: 0).")
    merge_base = merge_base.stdout.strip()

    # Committed changes since the branch left base, plus anything staged or
    # unstaged, so the same check works as a pre-push and a pre-commit guard.
    changed = set(git("diff", "--name-only", merge_base, "--").stdout.split())

    failures = []
    for module in modules_in_worktree():
        prefix = "" if module == "." else f"{module}/"
        relevant = [
            path for path in changed
            if path.startswith(prefix) and not exempt(path[len(prefix):])
        ]
        if not relevant:
            continue
        manifest = f"{prefix}__manifest__.py"
        try:
            with open(manifest, encoding="utf-8") as fh:
                new = version_of(fh.read())
        except ValueError as exc:
            failures.append(f"{manifest}: {exc}")
            continue
        # Against the tip of base, not the merge base: another merge may have
        # taken the next number since this branch was cut.
        previous = git("show", f"{base}:{manifest}", check=False)
        if previous.returncode:
            print(f"{module}: new on this branch, no bump needed.")
            continue
        try:
            old = version_of(previous.stdout)
        except ValueError:
            continue
        shown = lambda v: ".".join(map(str, v))
        if is_newer(new, old):
            print(f"{module}: {shown(old)} -> {shown(new)}")
            continue
        sample = ", ".join(sorted(relevant)[:3]) + (" ..." if len(relevant) > 3 else "")
        failures.append(
            f"{manifest}: version {shown(new)} is not higher than {shown(old)} on {base}, "
            f"but the module changed ({sample}). CloudPepper and Odoo.sh skip -u without "
            f"a higher version, so the database keeps the old schema. Bump it."
        )

    for failure in failures:
        prefix = "::error::" if os.environ.get("GITHUB_ACTIONS") else "ERROR: "
        print(prefix + failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
