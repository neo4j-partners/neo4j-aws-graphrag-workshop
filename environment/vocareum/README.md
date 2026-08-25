# Vocareum course assets

This directory holds everything Vocareum needs to run this workshop as a lab.
The workshop content lives beside it in this repository, so the course and its
lab definition stay in one place and move together.

## What each file is

- **`course.json`:** This file states the course key, the Vocareum course name
  and budget, the cleanup prefixes, and the pinned commit and file list the
  student starter package is built from.
- **`lab.template`:** CloudFormation runs this file in each student's AWS
  account at Start Lab. Vocareum submits it inline, so it must stay at or under
  51,200 bytes.
- **`expected.json`:** The ship gate reads this file to check that a started lab
  holds what it should.

## How the tooling finds this directory

The tooling lives in a separate private repository, `aws-vocareum`. That
repository holds one line naming this directory:

```
COURSE_ASSET_DIR=../neo4j-aws-graphrag-workshop/vocareum
```

The dependency runs one way. `aws-vocareum` reads this repository, and this
repository depends on nothing in `aws-vocareum`. A public repository cannot
install a private one, so a dependency in the other direction would fail for
everyone who clones this.

## Which commands read it

Run every command from a checkout of `aws-vocareum`, next to this one.

```bash
uv run vocareum-upload --dry-run --course graphrag       # reads lab.template
uv run vocareum-expect --no-start --course graphrag      # reads expected.json
uv run vocareum-package-startercode --course graphrag    # reads startercode
uv run vocareum-release --course graphrag                # reads all three
```

## Editing rules

- **Bump `startercode.commit` after changing workshop content.** The starter
  package is built from the pinned commit rather than the working tree, so an
  uncommitted edit never reaches a student. An unbumped commit ships the old
  files.
- **Update `startercode.paths` in the same edit when a listed path moves.** The
  list is passed to `git archive`, which fails on a path the pinned commit does
  not have.
- **Set `lab.template`'s `Metadata.SourceCommit` to the same commit.** The
  validator compares the two and refuses a release when they disagree.
- **Give any new dotfile a visible name.** Vocareum's extractor drops dotfiles.
  The build refuses to package one unless `aws-vocareum` names a visible
  replacement for it, so a dropped file stops a release instead of reaching a
  student as a missing file.
- **Check the template size after editing it.** Run
  `wc -c environment/vocareum/lab.template`. A file over 51,200 bytes fails at upload
  rather than at lint.
- **Keep `course_key` equal to `graphrag`.** The tooling refuses a definition
  whose key disagrees with the course it was asked for.
