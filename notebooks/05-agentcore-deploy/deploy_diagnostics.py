# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""What actually broke the remote container build, printed where the student is.

The starter toolkit builds the runtime image on CodeBuild rather than locally,
and when that build fails `Runtime.launch()` raises `RuntimeError: CodeBuild
failed with status: FAILED`. That sentence contains none of the information
needed to fix it. The Docker error text lives two API calls away, in the failed
phase's `contexts[].message` and in the build's CloudWatch log stream, and a
participant should not have to open the console to read it.

`report_build_failure()` makes those two calls and prints what they return. The
notebook wraps its launch in a `try` and calls this from the `except` before
re-raising, so the participant sees the real error immediately above the
toolkit's uninformative one.

This file is a sidecar next to the notebook rather than part of the `workshop`
package on purpose. That package is built into a wheel and copied into the
runtime container; this is a deploy-time diagnostic and has no reason to ship
inside the image. `workshop.bootstrap.start_module("05-agentcore-deploy")` puts
this module's directory on `sys.path`, so the notebook imports it by plain name.

It also runs on its own, for inspecting the last failed build without paying
another five minutes to reproduce it::

    python deploy_diagnostics.py --tail 80

IAM: the Vocareum participant policy in `environment/vocareum/lab.template`
already grants everything this needs. `ImageBuildProject` allows
`codebuild:ListBuildsForProject` and `codebuild:BatchGetBuilds` on
`arn:aws:codebuild:*:<account>:project/bedrock-agentcore-*` and the matching
`build/bedrock-agentcore-*`, and `BuildAndRuntimeLogs` allows
`logs:GetLogEvents` on `arn:aws:logs:*:<account>:log-group:/aws/codebuild/*`.
The CodeBuild project this notebook creates is named
`bedrock-agentcore-graphragbookingagent-builder`, which is inside that prefix.

Those IAM allows are not the last word. The lab account sits under an
organization service control policy that denies `codebuild:*` and `logs:*`
outside `us-east-1`, and an SCP denial overrides an IAM allow. A deploy in
any other region still builds, because the toolkit's own calls are made by a
different principal, but this report degrades to a single AccessDenied line.
That is the reason every call here is guarded rather than allowed to raise.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# The CodeBuild project name the toolkit derives from the Runtime name, spelled
# out so the standalone entry point needs no arguments in the common case. The
# notebook builds the same string in its setup cell as `CB_PROJECT`.
DEFAULT_PROJECT = "bedrock-agentcore-graphragbookingagent-builder"

# Only used by the command line path. The notebook always passes the region it
# resolved through `configure_aws_region()`. The value and the order it is
# reached in mirror `workshop.aws_region`, which this file deliberately does not
# import: running standalone from this directory puts only this directory on
# `sys.path`, so the `workshop` package is not importable here. A different
# default would send the standalone run looking for builds in a region the
# notebook never deployed to, and report "no builds" for a project that failed.
FALLBACK_REGION = "us-east-1"

RULE = "=" * 72


def _latest_build_id(codebuild: Any, project_name: str) -> str | None:
    """Return the newest build id for a project, or None if there is not one.

    Returns None rather than raising for every failure mode, including a project
    that has never built and an API call that is denied, because the caller is
    inside an `except` block and a second exception there would hide the first.
    """
    try:
        response = codebuild.list_builds_for_project(
            projectName=project_name, sortOrder="DESCENDING"
        )
    except (ClientError, BotoCoreError) as error:
        print(f"Could not list builds for {project_name}: {error}")
        return None

    ids = response.get("ids") or []
    if not ids:
        print(f"CodeBuild project {project_name} has no builds to report on.")
        return None
    return ids[0]


def _print_failed_phases(build: dict[str, Any]) -> None:
    """Print each failed phase and the context messages attached to it.

    The context message is the payload worth reading. For a failed DOWNLOAD or
    BUILD phase it carries the Docker or buildspec error verbatim, which is the
    one string that says what to fix.
    """
    phases = build.get("phases") or []
    failed = [phase for phase in phases if phase.get("phaseStatus") == "FAILED"]
    if not failed:
        print("\nNo phase is marked FAILED. The build log below is the next place")
        print("to look; a build can also fail on timeout with every phase clean.")
        return

    for phase in failed:
        name = phase.get("phaseType", "UNKNOWN")
        duration = phase.get("durationInSeconds")
        suffix = f" after {duration}s" if duration is not None else ""
        print(f"\nFAILED phase: {name}{suffix}")
        contexts = phase.get("contexts") or []
        if not contexts:
            print("  (no context message on this phase)")
            continue
        for context in contexts:
            status_code = context.get("statusCode", "")
            message = (context.get("message") or "").rstrip()
            if status_code:
                print(f"  statusCode: {status_code}")
            if message:
                for line in message.splitlines():
                    print(f"  {line}")


def _print_log_tail(build: dict[str, Any], region: str, tail_lines: int) -> None:
    """Print the tail of the build's CloudWatch stream, if it has one.

    A build that fails before the agent starts, on a denied source download for
    instance, never creates a stream, so both names are checked before the call
    is made.
    """
    logs_info = build.get("logs") or {}
    group_name = logs_info.get("groupName")
    stream_name = logs_info.get("streamName")
    if not group_name or not stream_name:
        print("\nThis build wrote no CloudWatch stream, so there is no log tail.")
        return

    print(f"\nLast {tail_lines} log lines from {group_name}/{stream_name}:")
    try:
        logs = boto3.client("logs", region_name=region)
        # startFromHead=False asks for the end of the stream. Within the page
        # that comes back, events are still ordered oldest first, so they print
        # in reading order with no reversal.
        response = logs.get_log_events(
            logGroupName=group_name,
            logStreamName=stream_name,
            startFromHead=False,
            limit=tail_lines,
        )
    except (ClientError, BotoCoreError) as error:
        print(f"  Could not read the build log: {error}")
        return

    events = response.get("events") or []
    if not events:
        print("  (the stream exists but is empty)")
        return
    for event in events:
        print(f"  {(event.get('message') or '').rstrip()}")


def report_build_failure(
    project_name: str, region: str, *, tail_lines: int = 80
) -> None:
    """Print why the newest CodeBuild build of a project failed.

    Safe to call from inside an `except` block: every AWS call is guarded and
    every failure is reported as one line of output, so this function never
    raises and never displaces the error the participant is already handling.

    Args:
        project_name: the CodeBuild project the toolkit created, for example
            `bedrock-agentcore-graphragbookingagent-builder`.
        region: the region the project lives in. The notebook passes the region
            it resolved during setup.
        tail_lines: how many trailing CloudWatch log lines to print. The
            default was measured against a real failed build rather than
            guessed. CodeBuild keeps writing after `docker build` fails, so
            the decisive error sits well above the end of the stream: a
            40-line tail landed entirely in the trailing chatter and never
            reached it.

    Returns:
        None. Everything it finds is printed.
    """
    print(f"\n{RULE}")
    print(f"CodeBuild diagnostics for {project_name} in {region}")
    print(RULE)

    try:
        codebuild = boto3.client("codebuild", region_name=region)
    except (ClientError, BotoCoreError) as error:
        print(f"Could not create a CodeBuild client: {error}")
        print(RULE)
        return

    build_id = _latest_build_id(codebuild, project_name)
    if build_id is None:
        print(RULE)
        return

    try:
        builds = codebuild.batch_get_builds(ids=[build_id])["builds"]
    except (ClientError, BotoCoreError) as error:
        print(f"Could not fetch build {build_id}: {error}")
        print(RULE)
        return
    except KeyError:
        print(f"The response for build {build_id} carried no 'builds' key.")
        print(RULE)
        return

    if not builds:
        print(f"Build {build_id} was listed but returned no detail.")
        print(RULE)
        return

    build = builds[0]
    start_time = build.get("startTime")
    print(f"build id:    {build.get('id', build_id)}")
    print(f"status:      {build.get('buildStatus', 'unknown')}")
    print(f"started:     {start_time if start_time is not None else 'unknown'}")

    _print_failed_phases(build)

    deep_link = (build.get("logs") or {}).get("deepLink")
    if deep_link:
        print(f"\nFull log in the console: {deep_link}")

    _print_log_tail(build, region, tail_lines)
    print(RULE)


def main() -> None:
    """Run the report from the command line against the last build."""
    parser = argparse.ArgumentParser(
        description=(
            "Print the failure detail of the newest CodeBuild build for the "
            "workshop's AgentCore runtime image."
        )
    )
    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        help=f"CodeBuild project name (default: {DEFAULT_PROJECT})",
    )
    parser.add_argument(
        "--region",
        default=(
            os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or FALLBACK_REGION
        ),
        help=(
            "AWS region (default: $AWS_REGION, then $AWS_DEFAULT_REGION, "
            f"then {FALLBACK_REGION})"
        ),
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=80,
        help="how many trailing log lines to print (default: 80)",
    )
    args = parser.parse_args()
    report_build_failure(args.project, args.region, tail_lines=args.tail)


if __name__ == "__main__":
    main()
