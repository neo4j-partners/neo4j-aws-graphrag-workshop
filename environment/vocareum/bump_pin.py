#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Move this course's pinned starter-code commit forward, in both files at once.

The pin lives in two places that must agree: ``startercode.commit`` in
``course.json`` and ``Metadata.SourceCommit`` in ``lab.template``. The release
tooling in the private ``aws-vocareum`` repository compares them and refuses a
mismatch, so editing one by hand and forgetting the other fails a release for a
reason that reads like a tooling bug. Bumping them together is the whole point
of this script.

It has no dependencies on purpose. This repository is public and cannot install
the private tooling that consumes the pin, so the one operation that has to
happen on this side of the seam does it with the standard library alone.

Two guards, both from real failures:

**A dirty tree is refused.** The package is built with ``git archive`` against
the pinned commit, so an uncommitted edit is invisible to it. Pinning HEAD with
an edit still in the working tree ships the old file and reports success.

**Every packaged path is checked at the target commit.** ``git archive`` fails
on a path that moved, and it fails during a release rather than here. A commit
that renames a listed path is caught before the pin changes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VOCAREUM_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = VOCAREUM_DIR.parents[1]
DEFINITION_PATH = VOCAREUM_DIR / "course.json"
TEMPLATE_PATH = VOCAREUM_DIR / "lab.template"

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")

# Both rewrites require exactly one match. A second `"commit"` key or a second
# `SourceCommit:` line means the file grew a shape this script does not
# understand, and guessing which one is the pin is how the two values drift.
DEFINITION_PIN = re.compile(r'("commit"\s*:\s*")(?P<sha>[0-9a-f]{40})(")')
TEMPLATE_PIN = re.compile(
    r"(?P<lead>^[ \t]*SourceCommit:[ \t]*)(?P<sha>[0-9a-f]{40})[ \t]*$",
    re.MULTILINE,
)


class BumpError(RuntimeError):
    """A refusal that names the file or the commit it is about."""


@dataclass(frozen=True)
class Pin:
    """The pinned commit as both files currently spell it."""

    definition: str
    template: str

    @property
    def agrees(self) -> bool:
        return self.definition == self.template


def git(*args: str) -> str:
    """Run one read-only git command in this repository."""
    result = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise BumpError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def read_pin() -> Pin:
    """Return the pin each file holds, without deciding which one is right."""
    definition = single_match(DEFINITION_PIN, DEFINITION_PATH.read_text("utf-8"))
    template = single_match(TEMPLATE_PIN, TEMPLATE_PATH.read_text("utf-8"))
    return Pin(definition=definition, template=template)


def single_match(pattern: re.Pattern[str], text: str) -> str:
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise BumpError(
            f"Expected exactly one pin matching {pattern.pattern!r}, found "
            f"{len(matches)}. Fix the file by hand rather than let this script "
            "guess which value is the pin."
        )
    return pattern.search(text).group("sha")  # type: ignore[union-attr]


def packaged_paths() -> list[str]:
    """Return the file list the student package is built from."""
    payload = json.loads(DEFINITION_PATH.read_text("utf-8"))
    block = payload.get("startercode")
    if not isinstance(block, dict):
        raise BumpError(f"{DEFINITION_PATH} has no startercode block to bump.")
    paths = block.get("paths")
    if not isinstance(paths, list) or not paths:
        raise BumpError(f"{DEFINITION_PATH} startercode.paths is empty.")
    return [str(path) for path in paths]


def assert_clean_tree() -> None:
    if git("status", "--porcelain"):
        raise BumpError(
            "The working tree has uncommitted changes. The package is built "
            "with git archive against the pinned commit, so an uncommitted "
            "edit ships nothing and reports success. Commit first, then bump."
        )


def resolve(revision: str) -> str:
    sha = git("rev-parse", revision)
    if not SHA_PATTERN.match(sha):
        raise BumpError(f"{revision!r} did not resolve to a full commit: {sha!r}")
    return sha


def assert_paths_exist(sha: str, paths: list[str]) -> None:
    """Refuse a target commit that moved a packaged path."""
    missing = [
        path
        for path in paths
        if not git("ls-tree", "-r", "--name-only", sha, path).strip()
    ]
    if missing:
        raise BumpError(
            f"Commit {sha[:12]} does not contain {', '.join(missing)}. "
            "git archive would fail during the release. Update "
            "startercode.paths in the same edit."
        )


def changed_packaged_paths(old: str, new: str, paths: list[str]) -> list[str]:
    """Return the packaged files that differ between the old and new pin.

    An empty list means the bump changes nothing a student receives, which is
    the normal case for a commit that only touched this directory. Printing it
    is the difference between believing a content fix shipped and knowing it.
    """
    if old == new:
        return []
    output = git("diff", "--name-only", f"{old}..{new}", "--", *paths)
    return sorted(line for line in output.splitlines() if line)


def write_pin(sha: str) -> None:
    for path, pattern in (
        (DEFINITION_PATH, DEFINITION_PIN),
        (TEMPLATE_PATH, TEMPLATE_PIN),
    ):
        text = path.read_text("utf-8")
        single_match(pattern, text)
        updated = pattern.sub(lambda match: rewrite(match, sha), text, count=1)
        path.write_text(updated, "utf-8")


def rewrite(match: re.Match[str], sha: str) -> str:
    """Replace only the SHA, so the surrounding formatting survives."""
    return match.group(0).replace(match.group("sha"), sha)


def report(pin: Pin, target: str, paths: list[str]) -> None:
    print(f"Repository      : {REPOSITORY_ROOT}")
    print(f"Pinned now      : {pin.definition}")
    if not pin.agrees:
        print(f"  lab.template  : {pin.template}  (disagrees)")
    print(f"Target commit   : {target}")
    changed = changed_packaged_paths(pin.definition, target, paths)
    if not changed:
        print("Packaged changes: none, the student package is unchanged")
        return
    print(f"Packaged changes: {len(changed)} file(s)")
    for path in changed:
        print(f"  {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--commit",
        default="HEAD",
        metavar="REV",
        help="Revision to pin. Defaults to HEAD.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Report drift and write nothing. Exits 1 when the two files "
            "disagree or the pin is behind the target."
        ),
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help=(
            "Bump anyway with uncommitted changes present. Only useful with "
            "--check, since the package cannot see those changes."
        ),
    )
    args = parser.parse_args(argv)

    try:
        pin = read_pin()
        paths = packaged_paths()
        target = resolve(args.commit)
        if not args.check and not args.allow_dirty:
            assert_clean_tree()
        assert_paths_exist(target, paths)
        report(pin, target, paths)

        if args.check:
            if pin.agrees and pin.definition == target:
                print("Pin is current.")
                return 0
            print("Pin needs a bump.")
            return 1

        if pin.agrees and pin.definition == target:
            print("Pin is already current. Nothing written.")
            return 0

        write_pin(target)
    except BumpError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print()
    print(f"Wrote {DEFINITION_PATH.name} and {TEMPLATE_PATH.name}.")
    print("Next, from this repository:")
    definition_rel = DEFINITION_PATH.relative_to(REPOSITORY_ROOT)
    template_rel = TEMPLATE_PATH.relative_to(REPOSITORY_ROOT)
    print(f"  git add {definition_rel} {template_rel}")
    print('  git commit -m "Bump the Vocareum starter-code pin"')
    print("Then release from aws-vocareum. See environment/vocareum/quick-release-workshop.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
