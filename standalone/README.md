# Run the Workshop in Your Own AWS Account

This directory deploys a browser-based AWS Code Editor for the **Grounded AI
Agents with Neo4j and AWS** workshop. The CloudFormation stack creates an EC2
development environment behind CloudFront, clones this repository into
`/workshop`, installs the notebook dependencies, and registers the `Workshop
(Python 3.13)` Jupyter kernel.

Neo4j is not hosted in AWS by this stack. Use an AuraDB instance and enter its
connection details in the cloned repository's `CONFIG.txt`.

## Before You Start

You need:

- An AWS account suitable for workshop experimentation. A dedicated sandbox
  account is preferable to an account containing sensitive workloads.
- AWS credentials available to the shell, through AWS IAM Identity Center,
  `AWS_PROFILE`, or environment variables.
- [`uv`](https://docs.astral.sh/uv/) installed on the computer from which you
  run the deployment.
- Amazon Bedrock model access for the workshop models in `us-east-1`.
- A default VPC with a public subnet that assigns public IP addresses, or an
  existing VPC and public subnet supplied in `.env`.
- Permission to create CloudFormation, IAM, EC2, SSM, Lambda, CloudFront, and
  S3 resources. CloudFormation is launched with `CAPABILITY_IAM`.

The template currently supports only `us-east-1` because its Amazon Linux 2023
AMI map contains that region only.

## Deploy

From the repository root:

```bash
cd standalone
./deploy.py
```

No `.env` file is required for the standard path. The deployment:

1. Uses `us-east-1` and the account's default VPC.
2. Creates an S3 bucket for staging the CloudFormation template if necessary.
3. Creates the `neo4j-graphrag-workshop` stack.
4. Clones this repository's `main` branch into `/workshop`.
5. Prints the Code Editor URL after the stack becomes available.

Deployment normally takes about 10 to 15 minutes. The IDE can become reachable
before dependency installation and Jupyter setup finish. Check bootstrap
progress with:

```bash
./deploy.py status
```

Wait until every reported bootstrap step is `Success` before running a
notebook.

## Open the Workshop

Open the `CodeEditorURL` printed by the deployment. It has this shape:

```text
https://example.cloudfront.net/?folder=/workshop&tkn=<login-token>
```

The complete URL is a bearer credential. Anyone who has it can open the IDE,
use the instance role, and read files stored on the instance. Do not publish it,
paste it into issue trackers, or commit it to the repository.

Inside the IDE:

1. Follow the repository's [main README](../README.md) to create an AuraDB Free
   instance and restore the workshop graph.
2. Fill in `/workshop/CONFIG.txt` with the AuraDB URI and password.
3. Open `notebooks/01-build-graph/1.1_build_graph.ipynb`.
4. Select the `Workshop (Python 3.13)` kernel if it is not selected already.

To verify AWS, Neo4j, Bedrock, and Python before starting Module 1, open an IDE
terminal and run:

```bash
cd /workshop/notebooks
uv run python ../setup/verify_setup.py
```

## Configuration Overrides

Copy the sample only when the defaults do not fit your account:

```bash
cp .env.sample .env
```

`deploy.py` loads `.env` from this directory. The file is ignored by Git.

| Setting | Default | Purpose |
|---|---|---|
| `STACK_NAME` | `neo4j-graphrag-workshop` | CloudFormation stack name and multi-student prefix |
| `AWS_REGION` | `us-east-1` | Deployment region; currently the only supported region |
| `TEMPLATE_BUCKET` | Account- and region-specific name | S3 bucket used to stage the template |
| `VPC_ID` | Default VPC | Existing VPC for the instance |
| `SUBNET_ID` | First public default-VPC subnet | Public subnet that assigns public IPs |
| `CODE_EDITOR_USER` | `participant` | Linux account running Code Editor |
| `INSTANCE_NAME` | `Neo4jGraphRAGWorkshop` | EC2 Name tag and hostname |
| `INSTANCE_TYPE` | `t4g.large` | EC2 instance type; x86 instance families are also supported |
| `INSTANCE_VOLUME_SIZE` | `40` | Root EBS volume size in GiB |
| `HOME_FOLDER` | `/workshop` | Repository clone target and initial IDE folder |
| `REPO_URL` | This repository | Git repository cloned during bootstrap |
| `REPO_BRANCH` | `main` | Branch or tag cloned during bootstrap |

Set `VPC_ID` and `SUBNET_ID` together or leave both blank. A custom subnet must
assign public IPs and route internet traffic through an internet gateway. The
instance needs outbound access for SSM registration, package installation, Git,
AWS APIs, and AuraDB.

## Commands

| Command | Result |
|---|---|
| `./deploy.py` | Creates or updates the single workshop stack |
| `./deploy.py status` | Shows stack outputs and SSM bootstrap progress |
| `./deploy.py delete` | Deletes the matching Code Editor stack or stacks |
| `./deploy.py --count N` | Creates `N` numbered stacks for a facilitated class |

`status` and `delete` find stacks by the `STACK_NAME` prefix. Choose a distinct
stack name so those commands do not match unrelated stacks.

## Clean Up

Delete the Code Editor stack when you finish:

```bash
./deploy.py delete
```

This stops the EC2 and CloudFront costs created by the standalone stack. It does
not remove:

- The S3 template-staging bucket.
- AWS resources created by Modules 4 and 5.
- The external AuraDB instance.

Follow the cleanup list in the repository's [main README](../README.md) for
module-created resources. Delete the auto-created staging bucket separately if
you no longer need it.

## Security Notes

The instance role has AWS managed `ReadOnlyAccess`, Bedrock invocation access,
and scoped write permissions used by Modules 4 and 5. Treat the IDE as a
privileged development environment in the target account.

The `--count` mode writes `<stack-name>-roster.csv` next to `deploy.py`. Each row
contains a bearer-token URL. These roster files are ignored by this repository,
but must still be stored and shared securely.

Multiple stacks in one AWS account are not isolated from one another. Students
can discover other stack URLs through CloudFormation and can affect workshop
resources that share the same naming patterns. For self-paced use, the intended
model is one student running one stack in their own AWS account.

## Troubleshooting

- **No default VPC:** Set `VPC_ID` and `SUBNET_ID` in `.env`.
- **Stack reaches `CREATE_COMPLETE`, but no notebook kernel appears:** Bootstrap
  is still running. Wait several minutes and run `./deploy.py status`.
- **`AccessDenied` during deployment:** The deploying identity lacks one of the
  required service or `iam:PassRole` permissions.
- **Bedrock `AccessDeniedException` in a notebook:** Confirm the workshop models
  are available in `us-east-1` and that the deployment is using that region.
- **Update cannot proceed from a failed state:** The script reports the failed
  state and asks you to run `./deploy.py delete` before recreating it.
