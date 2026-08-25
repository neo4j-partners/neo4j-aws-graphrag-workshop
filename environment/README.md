# Environment

Everything about standing up and checking a workshop environment lives here.
Which subfolder you need depends on where the workshop is running.

| Path | Who uses it | What it does |
|---|---|---|
| `verify.py` | every participant | Checks that this environment is ready for Module 1 |
| `own-account/` | a self-paced participant | Deploys a browser-based AWS Code Editor into their own AWS account |
| `vocareum/` | the facilitator | Course definition, lab template, and release pin for the hosted Vocareum labs |

## Quick start

Run the check after the Neo4j dump has been restored, the notebook dependencies
are installed, and the required AWS and Neo4j environment variables are set.

```bash
cd notebooks
uv venv && uv pip install -r requirements.txt
uv run python ../environment/verify.py
```

Continue to Module 1 only when it reports that all checks passed.

`verify.py` is **required; run it once per environment, and again after
changing credentials, Neo4j, the AWS region, or Bedrock model access.** It
verifies Python dependencies, the AWS identity, Neo4j connectivity and the
expected graph data, embedding access, and chat-model access.

Maintenance and release tooling is deliberately not here. It lives in `tools/`,
so that nothing in this folder is anything but a participant path.
