# Quick release: get workshop content in front of a student

This runbook publishes two artifacts to Vocareum: `lab.template` and the student
starter-code tree. Content edits reach a student only through a release. Nothing
here starts from the browser.

Two repositories are involved.

- **This repository** is public and holds the content plus the pin.
- **`aws-vocareum`** is private and holds every command that talks to Vocareum.

Run steps 1 to 4 here. Run steps 5 onward from `aws-vocareum`.

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

**The pin is always one commit behind HEAD.** Bumping it creates a new commit,
and that commit's own content cannot be inside the pin it just set. This is
harmless. Neither pin file is in `startercode.paths`, so nothing a student
receives changes.

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

## Steps

### 1. Commit your content edits

```bash
cd /Users/ryanknight/projects/aws/neo4j-aws-graphrag-workshop
git status --porcelain      # must be empty before step 3
git add -A && git commit -m "..."
```

The bump refuses a dirty tree. Committing first is not optional.

### 2. See what a bump would ship

```bash
uv run vocareum/bump_pin.py --check
```

It prints the current pin, the target commit, and every packaged file that
differs between them. Read that list. `Packaged changes: none` means the bump
changes nothing for a student, which is normal after a commit that only touched
`vocareum/`.

Exit codes: `0` the pin is current, `1` a bump is needed, `2` a refusal.

### 3. Write both pins

```bash
uv run vocareum/bump_pin.py
```

Pass `--commit REV` to pin something other than `HEAD`.

It refuses two things. A dirty working tree stops it, because the package cannot
see uncommitted work. A target commit that moved or renamed a path in
`startercode.paths` stops it, because `git archive` would fail later during the
release instead of here.

### 4. Commit the pin

```bash
git add vocareum/course.json vocareum/lab.template
git commit -m "Bump the Vocareum starter-code pin"
```

### 5. Build the package from the pin

```bash
cd /Users/ryanknight/projects/aws/aws-vocareum
uv run vocareum-package-startercode --course graphrag
```

Writes `startercode.zip` and `startercode.inventory.json` under
`.vocareum/build/graphrag/`. It makes no API call.

### 6. Run the offline gate

```bash
./scripts/validate_all.py
```

This covers both test suites, lint, formatting, and `cfn-lint` on both course
templates. Fix anything it reports before going further.

### 7. Preview

```bash
uv run vocareum-release --course graphrag
```

Local validation and a rebuilt archive. No API call, no upload.

### 8. Prepare

```bash
uv run vocareum-release --course graphrag --prepare
```

Read-only Vocareum calls. It saves the current remote template and the complete
current remote starter tree as rollback artifacts, then prints a line like:

```
Release ID             : 20260825T143000123456Z-abc123def456
```

**Copy that string.** It is a UTC timestamp plus twelve hex characters derived
from the digests of both artifacts. It names an evidence directory at
`.vocareum/releases/graphrag/<RELEASE_ID>/` holding `plan.json`,
`rollback-lab.template`, and `rollback-startercode.zip`.

`--apply` requires it so a plan cannot be applied that was not just prepared and
re-verified against the live remote. `--restore` takes the same ID to undo.

### 9. Apply

```bash
uv run vocareum-release --course graphrag --apply <RELEASE_ID>
```

This is the only step that writes. It replaces the starter tree, uploads the
template, waits for both writes, downloads every published file, verifies bytes
and nested paths, and saves one `deployment.json`.

### 10. Start the lab and walk it

Start Lab in Vocareum, then open the workspace. The new files are there now, and
not before. Walk `CONFIG.txt` and `setup/verify_setup.py` the way a student
would.

Starting a lab spends one launch against the budget.

### 11. Gate the stack

While that session is open:

```bash
uv run vocareum-expect --course graphrag
```

This reads the CloudFormation stack against `expected.json`. It says nothing
about starter-code content. The exit code is the answer.

### 12. Verify the published tree, then verify it again later

```bash
uv run vocareum-release --course graphrag --verify-live
```

Run this after step 10, and again hours later. On 2026-08-25 the starter tree was
published and byte-verified at 04:59Z, then found reverted to its clone-time
snapshot hours afterward, with the release evidence still reading success.
Vocareum can discard an API write after the fact. This mode is the only thing
that catches it. It exits 3 on any drift.

## If it goes wrong

```bash
uv run vocareum-release --course graphrag --restore <RELEASE_ID>
```

Restores both saved artifacts from that release's evidence directory. Keep the
release directory until the new content has passed a live student run.

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
uv run vocareum-release --course graphrag --prepare      # copy the Release ID
uv run vocareum-release --course graphrag --apply <RELEASE_ID>
uv run vocareum-release --course graphrag --verify-live
```

Then start the lab and walk it.
