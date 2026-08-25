# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""The AWS region, resolved once and exported under the name boto3 actually reads.

`AWS_REGION` is the name this workshop documents and the name `.env` carries, but
botocore does not read it. Its region lookup is the tuple
`('region', 'AWS_DEFAULT_REGION', None, None)`, so `AWS_REGION` is ignored and a
client built without an explicit `region_name` falls through to whatever region
the active AWS profile configures.

The clients that talk to Bedrock pass `region_name` explicitly and were never
affected. The ones that do not are `boto3.client("secretsmanager")` in
`hybrid_retrieval` and in `reservation_command`, which Modules 2 and 3 depend on.
A participant whose profile points somewhere other than the workshop region gets a
`ResourceNotFoundException` naming no region, which reads like a missing secret
rather than a misdirected lookup.

`configure_aws_region()` closes the gap at the source: it resolves the region once
and writes it back under both names, so unpinned clients land in the same region as
the pinned ones. Notebooks call it in their setup cell, where the participant can
see it happen.
"""

import os

DEFAULT_AWS_REGION = "us-east-1"


def aws_region() -> str:
    """Return the workshop region without touching the environment.

    `AWS_REGION` wins because it is the name the workshop documents and the one a
    participant edits in `.env`. `AWS_DEFAULT_REGION` is read next so that an
    environment configured the boto3 way is still honoured, and the constant is
    the fallback for a participant who set neither.
    """
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_AWS_REGION
    )


def configure_aws_region() -> str:
    """Resolve the region and export it under both names. Call once during setup.

    Returns the region, so a setup cell can print what it settled on. Writing both
    names is the point: the workshop's own code reads `AWS_REGION`, botocore reads
    `AWS_DEFAULT_REGION`, and leaving them to disagree is what sent a Secrets
    Manager lookup to the profile's region instead of the workshop's.

    This deliberately overrides a profile's configured region. The workshop pins a
    region because the models and the secrets live there, and a participant who
    genuinely wants a different one sets `AWS_REGION` rather than relying on
    whichever profile happens to be active.
    """
    region = aws_region()
    os.environ["AWS_REGION"] = region
    os.environ["AWS_DEFAULT_REGION"] = region
    return region
