# Changes Summary

## Overview

This workshop moved from AWS Workshop Studio to Vocareum. Vocareum gives each student a
JupyterLab environment and an AWS account. It does not give them a Neo4j database. So the
student now creates a free Neo4j database, restores the workshop graph into it, and pastes
the connection details into `CONFIG.txt`. Four changes make that work.

## What Changed

- **`README.md` now contains the full setup steps:** A Vocareum student receives only four
  things: `CONFIG.txt`, `README.md`, the `notebooks/` folder, and `setup/verify_setup.py`.
  The README used to link to setup pages that are not in that list. Those links went
  nowhere. The README now spells out all six setup steps directly, so the student never has
  to leave the file. Links that point outside the package now use full web addresses
  instead of file paths.

- **`vocareum/lab.template` grants the permissions Modules 4 through 6 need:** The lab role
  could call Amazon Bedrock and nothing else. Modules 4 and 5 create Lambda functions, IAM
  roles, secrets, container repositories, build projects, and AgentCore runtimes. Every one
  of those calls failed with an access denied error. Two new policies grant exactly those
  actions, each one limited to the resource name prefixes this workshop uses.

- **`vocareum/course.json` now lists what to delete after a lab ends:** The cleanup section
  was empty, so the resources Modules 4 and 5 create stayed running and kept costing money.
  It now lists the name prefixes of every resource the workshop creates. The sweeper matches
  on those prefixes and removes them.

- **`notebooks/workshop/graph_connection.py` prints a clear error message:** The old message
  ended with "Neither has a default" without saying what "neither" meant. It now names
  `NEO4J_URI` and `NEO4J_PASSWORD`, and explains why a missing value stops the run
  immediately instead of failing later.

## How This Was Checked

- **Repository lint passes:** `check_repo.py` reports all checks passed.
- **Test suite passes:** 214 tests pass.
- **Package links resolve:** The student package was rebuilt exactly as Vocareum builds it.
  All 14 file links inside it point at files that exist. Four of them were broken before.
- **Credentials against a live database:** `verify_setup.py` loaded `CONFIG.txt` and
  connected to a real AuraDB Free instance.

## Still To Do

- **Run Modules 4 and 5 in a live lab:** This is the only way to prove the new
  permissions work. Vocareum blocks the API call that would let a script check them.
- **Bump the release pin:** Run `uv run vocareum/bump_pin.py` and commit the result. The
  README changed, and the README ships to students, so the pin must move.
- **Rotate the Aura password:** It was exposed in a public commit and must be replaced.
