# Quick release: publish workshop content to Vocareum

This runbook publishes `lab.template` and the student starter-code tree. Content
edits reach a student only through this release; no browser publishing step is
involved.

Two repositories are involved.

- **This repository** is public and holds the content plus the pin.
- **`aws-vocareum`** is private and holds every command that talks to Vocareum.

Commit and pin content in this repository, then publish from `aws-vocareum`.

## What the pin is, and why it trails

The student package is built with `git archive` against one pinned commit. An
uncommitted edit is invisible to that build. So the pin is the only thing that
decides what a student receives.

The pin lives in two files that must agree.

| File | Field |
| --- | --- |
| `vocareum/course.json` | `startercode.commit` |
| `vocareum/lab.template` | `Metadata.SourceCommit` |

`aws-vocareum` compares them and refuses a mismatch. `vocareum/bump_pin.py`
writes both at once, which is why it exists.

Immediately after a bump, the pin is one commit behind `HEAD`: the bump commit
cannot point to itself. This is harmless because neither pin file is shipped in
`startercode.paths`.

## What ships, and what does not

`startercode.paths` in `course.json` is the whole list:

```
CONFIG.txt
README.md
notebooks
setup/verify_setup.py
```

`workshop-content/content/setup/*` is **not** in that list. Those pages are
Workshop Studio content and go out through that pipeline. A release does not
touch them.

## Release

### 1. Commit your content edits

```bash
cd /Users/ryanknight/projects/aws/neo4j-aws-graphrag-workshop
git status --porcelain      # must be empty before the bump
git add -A && git commit -m "..."
```

The bump refuses a dirty tree. Committing first is not optional.

### 2. Inspect and update the pin

```bash
uv run vocareum/bump_pin.py --check
```

Read the packaged-file diff before continuing. `Packaged changes: none` means
the target commit changes nothing a student receives.

Exit codes: `0` the pin is current, `1` a bump is needed, `2` a refusal.

```bash
uv run vocareum/bump_pin.py
git add vocareum/course.json vocareum/lab.template
git commit -m "Bump the Vocareum starter-code pin"
```

Pass `--commit REV` to pin a revision other than `HEAD`. The bump refuses a
dirty tree or a target that makes any configured starter-code path unavailable.

### 3. Run the offline gate

```bash
cd /Users/ryanknight/projects/aws/aws-vocareum
./scripts/validate_all.py
```

This runs both test suites, lint, formatting, and `cfn-lint`. Fix every failure
before publishing.

### 4. Publish

```bash
uv run vocareum-release --course graphrag --publish
```

This one command rebuilds and validates the package, saves both current remote
artifacts for rollback, re-verifies local and remote state, applies both new
artifacts, waits for the writes, and downloads the published files to verify
their bytes and paths.

Keep the printed release ID. Its evidence directory is
`.vocareum/releases/graphrag/<RELEASE_ID>/` and contains the plan, rollback
artifacts, and `deployment.json`.

For a release that needs a manual approval pause, use the equivalent split flow:

```bash
uv run vocareum-release --course graphrag --prepare
uv run vocareum-release --course graphrag --apply <RELEASE_ID>
```

The default command without a mode is an optional local-only preview:

```bash
uv run vocareum-release --course graphrag
```

### 5. Start the lab and walk it

Start Lab in Vocareum, then open the workspace. The new files are there now, and
not before. Walk `CONFIG.txt` and `setup/verify_setup.py` the way a student
would.

Starting a lab spends one launch against the budget.

### 6. Gate the stack

While that session is open:

```bash
uv run vocareum-expect --course graphrag
```

This reads the CloudFormation stack against `expected.json`. It says nothing
about starter-code content. The exit code is the answer.

### 7. Verify the published tree now and later

```bash
uv run vocareum-release --course graphrag --verify-live
```

Run this after the student walk and again hours later. On 2026-08-25 the starter
tree was published and byte-verified at 04:59Z, then found reverted to its
clone-time snapshot hours afterward, with the release evidence still reading
success. Vocareum can discard an API write after the fact. This mode is the
only thing that catches it. It exits 3 on any drift.

## If it goes wrong

```bash
uv run vocareum-release --course graphrag --restore <RELEASE_ID>
```

This restores both saved artifacts. Keep the release directory until the new
content has passed a live student run.

## Fast path

Content changed, and you already trust it:

```bash
cd /Users/ryanknight/projects/aws/neo4j-aws-graphrag-workshop
git add -A && git commit -m "..."
uv run vocareum/bump_pin.py
git add vocareum/course.json vocareum/lab.template
git commit -m "Bump the Vocareum starter-code pin"

cd /Users/ryanknight/projects/aws/aws-vocareum
./scripts/validate_all.py
uv run vocareum-release --course graphrag --publish
uv run vocareum-release --course graphrag --verify-live
```

Then start the lab, walk it, run `vocareum-expect`, and repeat `--verify-live`
later.
