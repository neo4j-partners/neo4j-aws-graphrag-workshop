# Setup

This folder contains only the participant-facing setup check. Run it after the
Neo4j dump has been restored, the notebook dependencies are installed, and the
required AWS and Neo4j environment variables are set.

## Quick start

```bash
cd notebooks
uv venv && uv pip install -r requirements.txt
uv run python ../setup/verify_setup.py
```

Continue to Module 1 only when it reports that all checks passed.

## Scripts, by importance and frequency

1. `verify_setup.py` — **required; run once per environment, and again after
   changing credentials, Neo4j, AWS region, or Bedrock model access.** Verifies
   Python dependencies, the AWS identity, Neo4j connectivity and expected graph
   data, embedding access, and chat-model access.

Maintenance and release tooling deliberately lives under the ignored
`workfolder/maintenance/` tree so it does not complicate the workshop setup.
