FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

# AWS_REGION and AWS_DEFAULT_REGION are both set, and to the same value.
# botocore reads only AWS_DEFAULT_REGION, so a container carrying just
# AWS_REGION builds a client that falls back to whatever region the task role
# resolves to. `workshop.aws_region` documents the whole trap. The launch step
# passes both again as container environment variables, which overrides these
# when the deploy targets a region other than us-east-1.
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    AWS_REGION=us-east-1 \
    AWS_DEFAULT_REGION=us-east-1

COPY agent_requirements.txt agent_requirements.txt
RUN uv pip install -r agent_requirements.txt

# `workshop-*.whl` is not in this directory in git. 5.1_deploy.ipynb builds it
# from notebooks/workshop/ and stages it here immediately before the build,
# because that package lives elsewhere in the repository and Docker cannot
# reach outside the build context. `--no-deps`: workshop's own dependencies
# are already pinned in agent_requirements.txt above, and reinstalling them
# here would resolve them a second time. Installed before the user switch
# below because system Python's site-packages, where this lands, is not
# writable by bedrock_agentcore.
COPY workshop-*.whl .
RUN uv pip install --no-deps workshop-*.whl

RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080

# No HEALTHCHECK: AgentCore Runtime manages container liveness itself, so one
# here would be redundant rather than forgotten.

# `reservation_command.py` is not in this directory in git either.
# 5.1_deploy.ipynb copies it here for the same reason. Listed explicitly
# rather than `COPY . .`, so the already-installed wheel above is not also
# picked up a second time as a loose file.
COPY --chown=bedrock_agentcore:bedrock_agentcore booking_agent.py reservation_command.py BUILD_INFO.txt ./

CMD ["opentelemetry-instrument", "python", "-m", "booking_agent"]
