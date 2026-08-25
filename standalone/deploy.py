#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "boto3>=1.35.0",
#     "python-dotenv>=1.0.1",
# ]
# ///
"""Launch the standalone AWS Code Editor stack in your own AWS account.

`code-editor.yaml` launches an EC2 instance running the AWS Code Editor server
behind nginx, with a CloudFront distribution as the TLS front door. It clones
the Grounded AI Agents with Neo4j and AWS workshop and launches into an
existing VPC.

Neo4j is never installed or hosted by this stack. Participants use Neo4j Aura
Free Tier, which is external to AWS.

Configuration can come from `.env` next to this script. See `.env.sample` for
the annotated list. Every setting is optional. `VPC_ID` and `SUBNET_ID` fall
back to the region's default VPC, and everything else falls back to a
workshop-ready default.

Two template parameters are resolved here rather than configured. `SubnetId`
comes from the default VPC when it is not set, and `PrefixListId` is always
looked up, since the CloudFront origin-facing prefix list has a different ID in
every region. There is no region allowlist in this script, but the template's
`AmiByRegion` map lists us-east-1 only, so another region needs an entry there.

One stack per student is the way to run this for a class. `--count` numbers the
stacks `<STACK_NAME>-01` upwards, spreads them round-robin over every public
subnet in the VPC so they land in different availability zones, and prints a
roster of student number to URL. Each stack derives its own login token from its
own `AWS::StackId`, so the URLs are distinct without any extra work. `status` and
`delete` find those stacks by name prefix, so neither needs `--count` repeated.

    ./deploy.py                 # create or update, wait, print the IDE URL
    ./deploy.py --count 5       # one stack per student, plus a roster and CSV
    ./deploy.py status          # stack state, outputs, and bootstrap progress
    ./deploy.py delete          # tear the stack down

Copy `.env.sample` to `.env` only when a default needs to be overridden.

CREATE_COMPLETE means the IDE answers. The stack's last resource polls `/healthz`
until the Code Editor server responds. The SSM bootstrap keeps running past that
point to finish Python 3.13, the pip packages, the Jupyter kernel, and the
extensions, which takes roughly another 5 to 10 minutes. `status` reports that
separately.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, WaiterError
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "code-editor.yaml"
ENV_PATH = SCRIPT_DIR / ".env"

# The security group pins ingress to the CloudFront origin-facing managed prefix
# list, and its ID differs per region. A hard-coded region-to-ID map in the
# template limited it to 17 regions and forced a matching allowlist here.
# Resolving it by name at deploy time removed both.
CLOUDFRONT_PREFIX_LIST_NAME = "com.amazonaws.global.cloudfront.origin-facing"

# Environment variable -> CloudFormation parameter. Unset or blank variables are
# omitted from the call, which falls back to the template default for everything
# except the network parameters below, which the template requires.
PARAMETER_ENV_MAP = {
    "CODE_EDITOR_USER": "CodeEditorUser",
    "INSTANCE_NAME": "InstanceName",
    "INSTANCE_TYPE": "InstanceType",
    "INSTANCE_VOLUME_SIZE": "InstanceVolumeSize",
    "HOME_FOLDER": "HomeFolder",
    "REPO_URL": "RepoUrl",
    "REPO_BRANCH": "RepoBranch",
    "VPC_ID": "VpcId",
    "SUBNET_ID": "SubnetId",
}

# Resolved from the region's default VPC when both are unset.
NETWORK_PARAMETERS = ("VpcId", "SubnetId")

# code-editor.yaml creates three IAM roles per stack: one for the SSM document
# Lambda, one for the instance, and one for the health check Lambda. Roles per
# account is the quota that caps class size, so the pre-flight check counts them.
ROLES_PER_STACK = 3

TERMINAL_FAILURE_STATES = frozenset(
    {
        "CREATE_FAILED", "ROLLBACK_COMPLETE", "ROLLBACK_FAILED",
        "UPDATE_ROLLBACK_COMPLETE", "UPDATE_ROLLBACK_FAILED", "DELETE_FAILED",
    }
)

# CloudFormation rejects update_stack in these states, so the stack has to be
# deleted and recreated. CREATE_FAILED is the common one: create_stack below
# passes OnFailure=DO_NOTHING so a bad create stays inspectable instead of
# rolling back, which means a failed first run always lands here.
# UPDATE_ROLLBACK_COMPLETE is absent on purpose, since that state is updatable.
UNUPDATABLE_STATES = frozenset(
    {"CREATE_FAILED", "ROLLBACK_COMPLETE", "ROLLBACK_FAILED", "DELETE_FAILED"}
)


class DeployError(Exception):
    """A configuration or AWS-side problem that should stop the run."""


@dataclass(frozen=True)
class Config:
    """Resolved settings for one invocation."""

    stack_name: str
    region: str
    bucket: str
    parameters: dict[str, str]


def load_config(account_id: str) -> Config:
    """Build a Config from `.env` plus the process environment."""
    region = os.environ.get("AWS_REGION") or "us-east-1"
    parameters = {
        param: value
        for env_var, param in PARAMETER_ENV_MAP.items()
        if (value := os.environ.get(env_var, "").strip())
    }

    bucket = os.environ.get("TEMPLATE_BUCKET", "").strip()
    return Config(
        stack_name=os.environ.get("STACK_NAME") or "neo4j-graphrag-workshop",
        region=region,
        bucket=bucket or f"neo4j-graphrag-workshop-{account_id}-{region}",
        parameters=parameters,
    )


def default_network(ec2) -> tuple[str, list[str]]:
    """Return the region's default VPC and every public subnet in it.

    Subnets come back sorted by availability zone. Students are handed one each
    in turn, so a single zone running out of instance capacity on the morning of
    a workshop takes down some of the class instead of all of it.
    """
    vpcs = ec2.describe_vpcs(
        Filters=[{"Name": "isDefault", "Values": ["true"]}]
    )["Vpcs"]
    if not vpcs:
        raise DeployError(
            "this region has no default VPC; set VPC_ID and SUBNET_ID in .env"
        )
    vpc_id = vpcs[0]["VpcId"]

    # The CloudFront origin is the instance PublicDnsName, so the subnet has to
    # auto-assign a public IP.
    subnets = ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "map-public-ip-on-launch", "Values": ["true"]},
        ]
    )["Subnets"]
    if not subnets:
        raise DeployError(
            f"default VPC {vpc_id} has no subnet that auto-assigns public IPs; "
            f"set VPC_ID and SUBNET_ID in .env"
        )
    subnets.sort(key=lambda subnet: subnet["AvailabilityZone"])
    return vpc_id, [subnet["SubnetId"] for subnet in subnets]


def cloudfront_prefix_list(ec2) -> str:
    """Return the ID of this region's CloudFront origin-facing prefix list."""
    prefix_lists = ec2.describe_managed_prefix_lists(
        Filters=[
            {"Name": "prefix-list-name", "Values": [CLOUDFRONT_PREFIX_LIST_NAME]}
        ]
    )["PrefixLists"]
    if not prefix_lists:
        raise DeployError(
            f"region {ec2.meta.region_name} has no {CLOUDFRONT_PREFIX_LIST_NAME} "
            f"managed prefix list, so the security group cannot be scoped to "
            f"CloudFront; deploy to a region that publishes one"
        )
    return prefix_lists[0]["PrefixListId"]


def resolve_parameters(session, cfg: Config) -> tuple[dict[str, str], list[str]]:
    """Return cfg.parameters with deploy-time lookups filled in, plus the
    subnets to rotate students over.

    An explicit SUBNET_ID in `.env` wins and every student lands there, since
    pinning the subnet is the whole point of setting it. Left unset, the default
    VPC supplies the full rotation.
    """
    parameters = dict(cfg.parameters)
    given = [name for name in NETWORK_PARAMETERS if name in parameters]
    if given and len(given) != len(NETWORK_PARAMETERS):
        raise DeployError("set both VPC_ID and SUBNET_ID, or neither")

    ec2 = session.client("ec2", region_name=cfg.region)
    if given:
        subnets = [parameters["SubnetId"]]
    else:
        parameters["VpcId"], subnets = default_network(ec2)
        parameters["SubnetId"] = subnets[0]
        print(f"Using default VPC {parameters['VpcId']}")
        print(f"Public subnets available: {', '.join(subnets)}")

    parameters["PrefixListId"] = cloudfront_prefix_list(ec2)
    return parameters, subnets


def expand(cfg: Config, count: int, subnets: list[str]) -> list[Config]:
    """Return one Config per student.

    A count of 1 keeps the plain stack name and the parameters untouched, so a
    single-student run behaves exactly as it did before `--count` existed.
    """
    if count == 1:
        return [cfg]

    students = []
    for number in range(1, count + 1):
        parameters = dict(cfg.parameters)
        parameters["SubnetId"] = subnets[(number - 1) % len(subnets)]
        # Without a suffix every instance carries the same Name tag, which makes
        # the EC2 console unreadable for a class.
        base_name = parameters.get("InstanceName", "CodeEditor")
        parameters["InstanceName"] = f"{base_name}-{number:02d}"
        students.append(
            replace(
                cfg,
                stack_name=f"{cfg.stack_name}-{number:02d}",
                parameters=parameters,
            )
        )
    return students


def check_role_headroom(session, count: int) -> None:
    """Stop before creating anything if the class cannot fit in the IAM quota.

    Roles per account is the tightest quota this stack touches. Failing here
    beats failing at student 12 of 20 and leaving a half-built class behind.
    """
    if count == 1:
        return

    try:
        summary = session.client("iam").get_account_summary()["SummaryMap"]
        used, quota = summary["Roles"], summary["RolesQuota"]
    except (ClientError, KeyError) as exc:
        print(f"Could not read the IAM role quota, continuing anyway: {exc}")
        return

    needed = count * ROLES_PER_STACK
    print(
        f"IAM roles: {used} of {quota} used, this run needs {needed} "
        f"for {count} students"
    )
    if used + needed > quota:
        affordable = max(0, (quota - used) // ROLES_PER_STACK)
        raise DeployError(
            f"{count} students need {needed} IAM roles but only "
            f"{quota - used} are left; this account fits {affordable} students "
            f"today. Raise the roles-per-account quota with a support request, "
            f"or delete unused roles."
        )


def ensure_bucket(s3, bucket: str, region: str) -> None:
    """Create the staging bucket if it does not already exist."""
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code not in {"404", "NoSuchBucket"}:
            raise DeployError(f"cannot access bucket {bucket}: {exc}") from exc

    print(f"Creating staging bucket {bucket}")
    kwargs: dict[str, object] = {"Bucket": bucket}
    # us-east-1 is the API default and rejects an explicit LocationConstraint.
    if region != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
    try:
        s3.create_bucket(**kwargs)
    except ClientError as exc:
        raise DeployError(f"could not create bucket {bucket}: {exc}") from exc


def stage_template(s3, cfg: Config) -> str:
    """Upload the template to S3 and return its URL."""
    if not TEMPLATE_PATH.is_file():
        raise DeployError(f"template not found: {TEMPLATE_PATH}")

    size = TEMPLATE_PATH.stat().st_size
    key = f"{cfg.stack_name}/{TEMPLATE_PATH.name}"
    print(f"Staging {TEMPLATE_PATH.name} ({size:,} bytes) in s3://{cfg.bucket}/{key}")

    with TEMPLATE_PATH.open("rb") as handle:
        s3.upload_fileobj(handle, cfg.bucket, key)
    return f"https://{cfg.bucket}.s3.{cfg.region}.amazonaws.com/{key}"


def describe_stack(cfn, stack_name: str) -> dict | None:
    """Return the stack description, or None if it does not exist."""
    try:
        response = cfn.describe_stacks(StackName=stack_name)
    except ClientError as exc:
        if "does not exist" in str(exc):
            return None
        raise
    return response["Stacks"][0]


def report_failures(cfn, stack_name: str, limit: int = 10) -> None:
    """Print the most recent failed stack events to explain a bad outcome."""
    try:
        events = cfn.describe_stack_events(StackName=stack_name)["StackEvents"]
    except ClientError as exc:
        print(f"Could not read stack events: {exc}", file=sys.stderr)
        return

    failures = [
        event
        for event in events
        if event["ResourceStatus"].endswith("_FAILED")
    ][:limit]
    if not failures:
        return

    print("\nMost recent failures:", file=sys.stderr)
    for event in failures:
        reason = event.get("ResourceStatusReason", "no reason given")
        print(
            f"  {event['LogicalResourceId']} ({event['ResourceType']}): {reason}",
            file=sys.stderr,
        )


def find_stacks(cfn, base: str) -> list[str]:
    """Return every live stack named `base` or `base-<suffix>`.

    Class size is a flag rather than a saved setting, so `status` and `delete`
    recover the set from CloudFormation instead of asking for `--count` again.
    This also catches stacks orphaned by a partly failed run. A stack that merely
    happens to share the prefix is picked up too, which is why `delete` prints
    what it found and asks before removing more than one.
    """
    names: set[str] = set()
    for page in cfn.get_paginator("list_stacks").paginate():
        for summary in page["StackSummaries"]:
            if summary["StackStatus"] == "DELETE_COMPLETE":
                continue
            name = summary["StackName"]
            if name == base or name.startswith(f"{base}-"):
                names.add(name)
    return sorted(names)


def wait_for_stack(cfn, stack_name: str, waiter_name: str) -> None:
    """Block until the named waiter succeeds, or raise DeployError."""
    print(f"  {stack_name}: waiting for {waiter_name.replace('_', ' ')}")
    waiter = cfn.get_waiter(waiter_name)
    try:
        waiter.wait(
            StackName=stack_name, WaiterConfig={"Delay": 20, "MaxAttempts": 120}
        )
    except WaiterError as exc:
        report_failures(cfn, stack_name)
        raise DeployError(
            f"stack {stack_name} did not reach the expected state"
        ) from exc


def stack_outputs(stack: dict) -> dict[str, str]:
    """Flatten a stack's Outputs list into a dict."""
    return {
        output["OutputKey"]: output["OutputValue"]
        for output in stack.get("Outputs", [])
    }


def print_outputs(stack: dict | None) -> None:
    # A create that failed before CloudFormation accepted it leaves no stack to
    # describe, and the caller reports that failure separately.
    if stack is None:
        print("Stack does not exist, so there are no outputs.")
        return

    outputs = stack_outputs(stack)
    if not outputs:
        print("Stack has no outputs yet.")
        return

    print("\nStack outputs")
    for key in sorted(outputs):
        print(f"  {key}: {outputs[key]}")

    if url := outputs.get("CodeEditorURL"):
        print(f"\nCode Editor: {url}")
        print(
            "The IDE answers as soon as the stack completes, but the SSM bootstrap\n"
            "keeps running for another 5 to 10 minutes to finish Python, the pip\n"
            "packages, the Jupyter kernel, and the extensions. If a notebook has no\n"
            "kernel yet, wait, then run: ./deploy.py status"
        )


def roster_rows(cfn, students: list[Config]) -> list[dict[str, str]]:
    """Collect student number, stack name, state, and URL for each student."""
    rows = []
    for number, student in enumerate(students, start=1):
        stack = describe_stack(cfn, student.stack_name)
        outputs = stack_outputs(stack) if stack else {}
        rows.append(
            {
                "student": f"{number:02d}",
                "stack": student.stack_name,
                "status": stack["StackStatus"] if stack else "NOT_CREATED",
                "url": outputs.get("CodeEditorURL", ""),
            }
        )
    return rows


def write_roster_csv(cfg: Config, rows: list[dict[str, str]]) -> Path:
    """Write the roster next to the script and return its path."""
    path = SCRIPT_DIR / f"{cfg.stack_name}-roster.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["student", "stack", "status", "url"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def print_roster(rows: list[dict[str, str]]) -> None:
    """Print the student-to-URL table that gets handed out to the class."""
    print("\nRoster")
    width = max(len(row["status"]) for row in rows)
    for row in rows:
        url = row["url"] or "no URL, see failures above"
        print(f"  {row['student']}  {row['status']:<{width}}  {url}")


def bootstrap_progress(session, cfg: Config) -> None:
    """Report the SSM command that installs the IDE after the instance boots."""
    resources = session.client("cloudformation", region_name=cfg.region)
    try:
        detail = resources.describe_stack_resource(
            StackName=cfg.stack_name, LogicalResourceId="CodeEditorInstance"
        )
    except ClientError:
        print("\nInstance not created yet, so no bootstrap to report.")
        return

    instance_id = detail["StackResourceDetail"].get("PhysicalResourceId")
    if not instance_id:
        print("\nInstance not created yet, so no bootstrap to report.")
        return

    ssm = session.client("ssm", region_name=cfg.region)
    try:
        invocations = ssm.list_command_invocations(
            InstanceId=instance_id, Details=False
        )
    except ClientError as exc:
        print(f"\nCould not read SSM invocations: {exc}")
        return

    print(f"\nBootstrap on {instance_id}")
    if not invocations["CommandInvocations"]:
        print("  No SSM command has started yet.")
        return

    for invocation in invocations["CommandInvocations"]:
        status = invocation["Status"]
        print(f"  {invocation['DocumentName']}: {status}")
        if status in {"Success", "Failed", "TimedOut", "Cancelled"}:
            print(f"    {invocation.get('StatusDetails', '')}")


def start_stack(cfn, student: Config, template_url: str) -> str:
    """Begin a create or update for one student.

    Returns the waiter to block on later, or an empty string when there is
    nothing to wait for.
    """
    parameters = [
        {"ParameterKey": key, "ParameterValue": value}
        for key, value in sorted(student.parameters.items())
    ]

    existing = describe_stack(cfn, student.stack_name)
    if existing and (status := existing["StackStatus"]) in UNUPDATABLE_STATES:
        raise DeployError(
            f"stack {student.stack_name} is in {status} and cannot be updated; "
            f"run './deploy.py delete' first"
        )

    call = {
        "StackName": student.stack_name,
        "TemplateURL": template_url,
        "Parameters": parameters,
        "Capabilities": ["CAPABILITY_IAM"],
    }

    if existing:
        print(f"  {student.stack_name}: updating")
        try:
            cfn.update_stack(**call)
        except ClientError as exc:
            if "No updates are to be performed" in str(exc):
                print(f"  {student.stack_name}: no changes to apply")
                return ""
            raise DeployError(f"update failed: {exc}") from exc
        return "stack_update_complete"

    print(f"  {student.stack_name}: creating")
    try:
        # DO_NOTHING leaves a failed stack in CREATE_FAILED instead of
        # rolling back, so report_failures can still name the culprit.
        cfn.create_stack(**call, OnFailure="DO_NOTHING")
    except ClientError as exc:
        raise DeployError(f"create failed: {exc}") from exc
    return "stack_create_complete"


def deploy(session, cfg: Config, count: int) -> None:
    """Create or update one stack per student."""
    cfn = session.client("cloudformation", region_name=cfg.region)
    s3 = session.client("s3", region_name=cfg.region)

    check_role_headroom(session, count)

    resolved, subnets = resolve_parameters(session, cfg)
    students = expand(replace(cfg, parameters=resolved), count, subnets)

    ensure_bucket(s3, cfg.bucket, cfg.region)
    # One upload for the whole class. Every stack reads the same object.
    template_url = stage_template(s3, cfg)

    # A pinned SUBNET_ID is shared by the whole class, so it stays in this list.
    per_student = set()
    if count > 1:
        per_student = {"InstanceName"} | ({"SubnetId"} if len(subnets) > 1 else set())

    print("Shared parameters:")
    for key, value in sorted(resolved.items()):
        if key not in per_student:
            print(f"  {key}={value}")
    if count > 1 and len(subnets) > 1:
        print(f"Rotating students over {len(subnets)} subnets, one each in turn")

    print(f"\nStarting {len(students)} stack(s) in {cfg.region}")
    pending: list[tuple[Config, str]] = []
    failures: dict[str, str] = {}
    for student in students:
        try:
            if waiter_name := start_stack(cfn, student, template_url):
                pending.append((student, waiter_name))
        except DeployError as exc:
            # One student's stack failing must not cost the rest of the class.
            print(f"  {student.stack_name}: {exc}", file=sys.stderr)
            failures[student.stack_name] = str(exc)

    if pending:
        # CloudFormation builds them all at once, so waiting one at a time costs
        # the slowest stack rather than the sum. This takes 10 to 15 minutes.
        print(f"\nWaiting on {len(pending)} stack(s), 10 to 15 minutes")
        for student, waiter_name in pending:
            try:
                wait_for_stack(cfn, student.stack_name, waiter_name)
            except DeployError as exc:
                failures[student.stack_name] = str(exc)

    if count == 1:
        print_outputs(describe_stack(cfn, cfg.stack_name))
    else:
        rows = roster_rows(cfn, students)
        print_roster(rows)
        csv_path = write_roster_csv(cfg, rows)
        print(f"\nRoster written to {csv_path}")
        print(
            "\nThe IDEs answer as soon as their stack completes, but each SSM\n"
            "bootstrap keeps running for another 5 to 10 minutes to finish Python,\n"
            "the pip packages, the Jupyter kernel, and the extensions."
        )

    if failures:
        raise DeployError(
            f"{len(failures)} of {len(students)} stack(s) failed: "
            f"{', '.join(sorted(failures))}"
        )


def show_status(session, cfg: Config) -> None:
    """Print state, outputs, and bootstrap progress for every student stack."""
    cfn = session.client("cloudformation", region_name=cfg.region)
    names = find_stacks(cfn, cfg.stack_name)
    if not names:
        raise DeployError(
            f"no stack named {cfg.stack_name} or {cfg.stack_name}-NN in {cfg.region}"
        )

    print(f"Region: {cfg.region}")
    print(f"Found {len(names)} stack(s) matching {cfg.stack_name}")

    # Full detail for a single stack. A class gets one line each, since twenty
    # bootstrap reports is a wall of text nobody reads.
    for name in names:
        stack = describe_stack(cfn, name)
        if stack is None:
            continue
        status = stack["StackStatus"]

        if len(names) == 1:
            print(f"\nStack:  {name}")
            print(f"Status: {status}")
            if status in TERMINAL_FAILURE_STATES:
                report_failures(cfn, name)
            print_outputs(stack)
            bootstrap_progress(session, replace(cfg, stack_name=name))
            continue

        url = stack_outputs(stack).get("CodeEditorURL", "no URL yet")
        print(f"  {name}  {status}  {url}")
        if status in TERMINAL_FAILURE_STATES:
            report_failures(cfn, name, limit=3)


def delete_stacks(session, cfg: Config, assume_yes: bool) -> None:
    """Delete every student stack and wait for them all to go away."""
    cfn = session.client("cloudformation", region_name=cfg.region)
    names = find_stacks(cfn, cfg.stack_name)
    if not names:
        print(f"No stack matching {cfg.stack_name} in {cfg.region}, nothing to do.")
        return

    print(f"About to delete {len(names)} stack(s) in {cfg.region}:")
    for name in names:
        print(f"  {name}")

    # The prefix match can catch a stack that merely shares the name, so confirm
    # before removing a whole class. A single stack is the unambiguous case.
    if len(names) > 1 and not assume_yes:
        try:
            answer = input("Delete all of these? Type yes to continue: ").strip()
        except EOFError:
            # Piped or non-interactive, where silence must not mean yes.
            raise DeployError(
                "deleting more than one stack needs confirmation, and there is no "
                "terminal to ask on; pass --yes to confirm up front"
            ) from None
        if answer != "yes":
            print("Nothing deleted.")
            return

    failures: dict[str, str] = {}
    for name in names:
        try:
            cfn.delete_stack(StackName=name)
        except ClientError as exc:
            print(f"  {name}: delete failed: {exc}", file=sys.stderr)
            failures[name] = str(exc)

    if len(failures) < len(names):
        print(f"\nWaiting on {len(names) - len(failures)} deletion(s)")
    for name in names:
        if name in failures:
            continue
        try:
            wait_for_stack(cfn, name, "stack_delete_complete")
        except DeployError as exc:
            failures[name] = str(exc)

    if failures:
        raise DeployError(
            f"{len(failures)} stack(s) did not delete: {', '.join(sorted(failures))}"
        )
    print("Deleted.")


def positive_int(value: str) -> int:
    """argparse type for --count."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="deploy",
        choices=("deploy", "status", "delete"),
        help="what to do (default: deploy)",
    )
    parser.add_argument(
        "--count",
        type=positive_int,
        default=1,
        metavar="N",
        help=(
            "number of student stacks to deploy, named <STACK_NAME>-01 upwards "
            "(default: 1, which keeps the plain stack name). Ignored by status "
            "and delete, which find the stacks by name prefix."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the confirmation prompt when deleting more than one stack",
    )
    return parser


def main() -> int:
    # Python block-buffers stdout when it is not a tty, which hides all progress
    # when this script is piped, redirected, or run in CI until it exits.
    sys.stdout.reconfigure(line_buffering=True)

    args = build_parser().parse_args()

    if ENV_PATH.is_file():
        load_dotenv(ENV_PATH)
        print(f"Loaded {ENV_PATH}")
    else:
        print(f"No {ENV_PATH.name} found, using environment and template defaults")

    session = boto3.Session()
    try:
        identity = session.client("sts").get_caller_identity()
    except ClientError as exc:
        print(f"AWS credentials are not usable: {exc}", file=sys.stderr)
        return 1

    cfg = load_config(identity["Account"])
    print(f"Account {identity['Account']} as {identity['Arn'].rsplit('/', 1)[-1]}")

    try:
        match args.command:
            case "deploy":
                deploy(session, cfg, args.count)
            case "status":
                show_status(session, cfg)
            case "delete":
                delete_stacks(session, cfg, args.yes)
    except DeployError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ClientError as exc:
        print(f"AWS error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
