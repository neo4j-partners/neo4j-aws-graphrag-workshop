# Shared AWS Account Workshop Proposal

## Why We Are Doing This

Vocareum is unavailable for this workshop. The class must use one existing AWS
account. The current `environment/own-account` deployment grants broad AWS
access to each browser IDE. A shared class needs narrower access.

The core goal is to keep the simple browser experience and the real AgentCore
lessons. Each attendee must be limited to their own workshop resources. The
organizer must create all IAM roles and other privileged resources before the
class starts.

## Summary

- **Current risk:** Treat `environment/own-account` as high risk for a shared class. Its broad AWS and IAM access can lead to account-wide control.
- **Recommendation:** Build the restricted shared-account version before running a multi-attendee class.
- **Deployment target:** Build the new deployment in `environment/shared-account`.
- **Account model:** Run every attendee environment in one AWS account.
- **Attendee access:** Give each attendee one private browser IDE link.
- **AWS boundary:** Give each IDE a separate role with access to exact resources.
- **Organizer access:** Use the administrator profile only from the organizer computer.
- **Module 4:** Precreate the secret, Lambda shells, service roles, Gateway, and two targets.
- **Module 5:** Precreate the build lane, image repository, Runtime, and deployment broker.
- **Attendee work:** Let attendees update code, build an image, deploy an agent, and test it.
- **Main control:** Remove all attendee IAM administration and broad account access.
- **Notebook changes:** Remove privileged creation steps and their AWS permissions. Removing notebook cells alone does not block direct API calls.
- **Browser login:** Use a short-lived bearer link. Protect it with private handling and CloudFront controls.
- **Source deployment:** Keep `environment/own-account` unchanged for its current use.

## Goal

- Provide one ready-to-use browser IDE for each attendee.
- Preserve the learning goals in Modules 1 through 6.
- Preserve real Lambda, AgentCore Gateway, CodeBuild, ECR, and AgentCore Runtime work.
- Prevent one attendee from reading or changing another attendee's AWS resources.
- Prevent attendee code from gaining administrator access.
- Make setup, health checks, class operations, and cleanup manageable for one organizer.

## Scope

This proposal covers the new deployment under `environment/shared-account`. It
covers the browser IDE, AWS resources, IAM boundaries, notebook changes,
validation, class rollout, and cleanup.

This proposal leaves the existing `environment/own-account` path in place. It
also leaves AuraDB outside AWS. The AuraDB isolation choice appears as an
explicit prerequisite because AWS IAM cannot isolate data inside a shared AuraDB
credential.

## Assumptions

- The workshop runs in `us-east-1`.
- The organizer deploys with `AWS_PROFILE=AdministratorAccess-159878781974`.
- The organizer keeps those profile credentials off every attendee instance.
- Each attendee receives a separate EC2 instance, CloudFront distribution, IDE
  token, instance role, and resource set.
- Attendees can run any shell command and any Python code inside their own IDE.
- Attendees can intentionally read their own instance role credentials.
- Attendees can intentionally change the Lambda and Runtime code assigned to them.
- The instance role is the primary AWS security boundary.
- The class size is known before deployment.
- The workshop region has access to the required Bedrock models.
- The AWS account has enough service quota for the full class plus a safety margin.
- A bearer link is an accepted login method for this event.
- The organizer can delete all workshop resources soon after the event.

## Live AWS Check

On August 25, 2026, we checked the account with read-only AWS calls. The results
support this design. The check changed no resources and invoked no models.

- **Organizer identity:** The profile uses an AWS SSO AdministratorAccess role in account `159878781974`.
- **Organizer permissions:** The role can create and manage every service required by this proposal.
- **AgentCore proof:** The account already has a ready Runtime and Gateway. It also has two targets, Lambda tools, an ECR repository, and a CodeBuild project.
- **Template support:** CloudFormation supports Gateway, Gateway target, and Runtime resources in this account.
- **Model access:** The required Claude, Nova embedding, and Titan embedding access is available in `us-east-1`.
- **Main capacity limit:** IAM has 596 role slots available. Each attendee needs six roles. This supports at most 99 attendees before subtracting shared roles and the safety reserve.
- **Helper role impact:** Keeping two helper roles from `environment/own-account` raises the count to eight roles per attendee. This lowers the limit to 74 before the safety reserve.
- **Other capacity:** The checked quotas for the other workshop services have more room than IAM. These include EC2, CloudFront, Lambda, CodeBuild, ECR, Secrets Manager, CloudFormation, SSM, Gateway, Runtime, and targets.
- **Final class limit:** The final attendee count depends on the completed template role count, shared resources, and a safety reserve.
- **Burst limit:** AWS limits how quickly stacks and AgentCore resources can be created. Pace creation requests and retry temporary throttling.

The live check shows that the organizer account can build the deployment. Phase 0
must still use the final class size and template to set the safe attendee limit.

## Security Model

### Organizer boundary

The organizer deployment creates every IAM role and every privileged service
resource. The administrator profile stays on the organizer computer. The
deployment must never copy long-lived AWS credentials into CloudFormation,
instance user data, SSM parameters, logs, roster files, or notebooks.

The organizer controls the resource templates, fixed service roles, fixed build
projects, approved repository revision, and cleanup workflow.

### Attendee boundary

Each attendee gets a stable attendee ID. That ID appears in resource names,
tags, stack names, log groups, and the roster. Each instance role names only the
resources for that attendee.

The attendee role has no IAM administration. It cannot create, edit, attach,
detach, or delete roles and policies. It can pass only its own CodeBuild role
if CodeBuild requires that action. The pass permission limits the attendee to
one role and the CodeBuild service that uses it.

The attendee role has no broad managed read policy. It has no broad access to
CloudFormation, EC2, S3, Secrets Manager, Lambda, ECR, CodeBuild, CloudWatch,
CloudFront, or AgentCore.

The attendee role can invoke only the required Bedrock models. The policy uses
the exact model or inference profile resources required by the notebooks.

The attendee role cannot call the Runtime update API. It invokes one fixed
deployment broker. The broker accepts only an approved image from that
attendee's repository. It fixes the Runtime role, network mode, protocol,
environment, and authorization settings.

### Service role boundary

Every attendee gets separate Lambda, Gateway, CodeBuild, Runtime, and deployment
broker service roles. No execution role is shared between attendees. This rule
contains arbitrary attendee code within one resource set.

The Lambda role can read only that attendee's Neo4j secret and write only its
own logs. The Gateway role can invoke only that attendee's two Lambda functions.
The CodeBuild role can read only that attendee's build input, push only to that
attendee's ECR repository, and write only its own logs. The Runtime role can
pull only approved bootstrap images and images from that attendee's repository.
It can use only the required Bedrock models, the attendee secret, its own logs,
and other explicit Runtime dependencies.

The deployment broker role can update only that attendee's Runtime and pass
only that attendee's Runtime role to AgentCore. The broker rejects any request
that names another repository, Runtime, role, network, protocol, or environment.

### Browser boundary

Each IDE uses a separate, high-entropy token. The roster is the only organizer
artifact that maps attendees to full bearer links. Attendee roles cannot read
CloudFormation outputs, token secrets, or other attendee stacks.

CloudFront adds a unique origin header for each environment. Nginx rejects
requests without the expected header. The instance security group accepts web
traffic only from the CloudFront origin-facing prefix list.

The deployment requires IMDSv2. It encrypts the EBS volume. It removes attendee
sudo access. It disables access between attendee instances. It pins the
workshop checkout to a reviewed revision and installs locked dependencies.

Set every token to expire shortly after the class. The organizer can rotate an
individual token by updating or replacing that attendee environment. The
organizer deletes all environments after the class.

## Per-Attendee Resource Set

Each attendee receives the following resources:

- One browser IDE EC2 instance and encrypted volume.
- One CloudFront distribution and one private login token.
- One instance role with an exact attendee policy.
- One Neo4j secret.
- Two Lambda function shells and one Lambda execution role scoped to those two
  functions.
- One AgentCore Gateway, two Gateway targets, and one Gateway execution role.
- One attendee build prefix in the workshop staging bucket.
- One ECR repository.
- One fixed CodeBuild project and one CodeBuild execution role.
- One AgentCore Runtime role.
- One precreated AgentCore Runtime that starts with an approved bootstrap image.
- One deployment broker Lambda and one narrow broker role.
- Dedicated log groups with short retention.
- Consistent workshop and attendee tags.

Limit shared resources to the template staging bucket, the optional CloudFront
WAF policy, approved artifacts, and organizer deployment state. Shared
resources must not grant one attendee access to another attendee's data.

## Module 4 Experience

The organizer precreates the Neo4j secret, two Lambda function shells, the
Lambda execution permissions, the Gateway execution role, one Gateway, and two
placeholder targets for each attendee.

The attendee completes these real deployment tasks:

- Save or verify their own Neo4j connection details in their exact secret.
- Package the two tool implementations from the workshop source.
- Update the code in their two existing Lambda functions.
- Invoke each Lambda function and inspect its own logs.
- Update the two target configurations in their own Gateway.
- Inspect the targets and confirm that they are ready.
- Connect to their Gateway with IAM authentication.
- Run the Strands agent against the deployed Gateway tools.

The attendee cannot create a Lambda function. The attendee cannot change a
Lambda function role, environment, network, layer, timeout, memory, or reserved
concurrency. The attendee cannot update the Gateway role. The attendee cannot
invoke another attendee's functions or Gateway.

The Gateway role provides a second boundary. A target that points at another
Lambda cannot run because the Gateway role can invoke only the two assigned
functions. Precreated targets also limit quota use and keep cleanup under stack
control.

## Module 5 Experience

The organizer precreates one controlled build lane for each attendee. The lane
contains an S3 input prefix, an ECR repository, a fixed CodeBuild project, a
narrow CodeBuild role, a narrow Runtime role, an AgentCore Runtime that starts
with an approved bootstrap image, and a narrow deployment broker.

The attendee completes these real deployment tasks:

- Prepare the agent source and container build input.
- Configure the agent to fetch its own Neo4j secret by ARN.
- Upload the build input to their assigned S3 prefix.
- Start their assigned CodeBuild project.
- Watch the real container build and inspect its own logs.
- Verify that the image has a new immutable tag in their assigned ECR repository.
- Ask their deployment broker to deploy the new image to their Runtime.
- Wait for the Runtime update to become ready.
- Invoke the deployed agent through its default qualifier.
- Run the workshop smoke tests and inspect correlated logs.

The attendee cannot create or change a CodeBuild project. The attendee cannot
change the CodeBuild service role. The attendee cannot push to another ECR
repository. The attendee cannot create or delete a Runtime. The attendee cannot
call the Runtime update API directly. The attendee cannot update or invoke
another attendee's Runtime.

The Module 5 notebook uses direct AWS API calls for the controlled build and
deployment broker. The installed starter toolkit creates and updates resources
outside the attendee boundary. The notebook teaches packaging, building,
deployment, invocation, and debugging.

The CodeBuild project can run attendee-controlled build input. Its service role
therefore stays narrow even when the build is malicious. The project uses a
small compute type, a short timeout, and limited concurrent work.

The Runtime can run attendee-controlled agent code. Its role therefore grants
only the exact Runtime dependencies for that attendee. An attendee may break
their own Runtime. The organizer can restore it without affecting the class.

The Runtime environment contains the attendee secret ARN instead of the Neo4j
password. The Runtime fetches the password from that exact secret. This keeps
the password out of Runtime settings that the attendee can inspect.

The broker accepts only an immutable image tag or digest from the attendee's
repository. It supplies the fixed Runtime role, public network mode, protocol,
secret ARN, and other approved environment settings.

Validation must confirm that the broker selects the new image and the default
qualifier invokes the updated Runtime. The notebook must use that confirmed
flow without creating a new Runtime.

## AuraDB Isolation

A separate AuraDB instance or isolated credential per attendee is the required
design for full attendee isolation. Each AWS secret then contains only that
attendee's credential.

A shared AuraDB credential gives every attendee access to the same graph. One
attendee can then change another attendee's data. AWS IAM cannot prevent that
effect. If the class uses a shared credential, use a disposable graph, explain
the shared state, keep a clean restore point, and plan a fast reset procedure.

The organizer must choose the AuraDB model before implementation. A shared
graph requires a deliberate redesign because Modules 1, 3, 5, and 6 can change
data used by other attendees. Namespacing, reset, and recovery must be part of
that design.

## Cost and Quota Controls

- Check EC2, IAM role, CloudFront distribution, Lambda, CodeBuild, ECR,
  AgentCore Gateway, and AgentCore Runtime quotas before the event.
- Calculate required quota from the class size and the resources per attendee.
- Keep capacity for organizer testing and failed replacements.
- Request quota increases well before the event when required.
- Add an account budget and cost anomaly alerts for the workshop period.
- Budget alerts can arrive after spend occurs. They do not cap spending.
- Restrict Bedrock invocation to the workshop models.
- Set short Lambda timeouts and low reserved concurrency.
- Use small CodeBuild compute and short build timeouts.
- Limit each attendee to one fixed CodeBuild project and one fixed Runtime.
- Add ECR lifecycle rules that retain only the required recent images.
- Add S3 lifecycle rules that expire build inputs after the event.
- Set short CloudWatch log retention.
- Tag every resource with the workshop ID, attendee ID, owner, and expiration time.
- Run a scheduled organizer check for unexpected tagged resources and active builds.
- Publish a stop procedure for unusual spend during the class.

## Risks

- **Bearer link sharing:** A person with an active link controls that attendee IDE. Short token expiry, private roster handling, fast rotation, and immediate environment deletion reduce this risk.
- **Arbitrary attendee code:** Lambda, CodeBuild, and Runtime execute attendee-controlled code. Separate narrow execution roles contain the effect.
- **Service permission gaps:** Some AgentCore actions may need broad discovery access. Test each action against exact resources before implementation.
- **Runtime update behavior:** A live pilot must confirm image updates and invocation through the default qualifier.
- **Runtime configuration:** An update can request role, network, protocol, environment, or authorization changes. The deployment broker fixes every sensitive setting.
- **Gateway target behavior:** A target update may reference an unexpected resource. The narrow Gateway role prevents it from invoking other functions.
- **CodeBuild overrides:** A build request accepts overrides and runs attendee code. The narrow build role limits what that code can access. Exact pass permissions block other service roles.
- **Shared AuraDB state:** A shared credential permits cross-attendee graph changes. Separate credentials or disposable shared data address this risk.
- **Account quota:** A large class can exhaust service quotas. Preflight calculations and a smaller pilot catch this early.
- **Account cost:** Bedrock, Runtime, CodeBuild, CloudFront, EC2, and logs create real cost. Limits, alerts, monitoring, and immediate cleanup reduce this risk.
- **Bootstrap supply chain:** A moving branch or unpinned installer can change class code. A reviewed commit, locked dependencies, and verified downloads reduce this risk.
- **Cleanup gaps:** ECR images, S3 objects, logs, targets, and Runtime state can block deletion or keep charging. Stack ownership, lifecycle rules, and a final account scan address this risk.
- **Organizer credential exposure:** An administrator credential in an IDE gives that attendee account-wide access. Deployment uses the local AWS profile and never exports its credentials to the class environment.

## Phase Checklist

### Phase 0: Confirm Feasibility and Class Inputs

**Status:** Pending

**Outcome:** The team has confirmed the account, class size, region, quotas,
AgentCore permission behavior, AuraDB model, and accepted browser risk.

**Checklist:**

- [ ] Record the planned attendee count and reserve count.
- [ ] Confirm `us-east-1` and required Bedrock model access.
- [ ] Calculate the full per-service quota requirement.
- [ ] Check current quota and request increases where needed.
- [ ] Test current AgentCore Gateway and Runtime APIs with representative exact resources.
- [ ] Confirm that attendee target operations can stay inside one Gateway.
- [ ] Confirm that the broker can update an existing Runtime while attendee create, update, and delete actions remain blocked.
- [ ] Confirm how the default qualifier invokes the updated Runtime.
- [ ] Confirm the minimum exact role pass permission for CodeBuild.
- [ ] Confirm that CodeBuild rejects every unapproved service role override.
- [ ] Set the class limit from the final role count and keep a safety reserve.
- [ ] Choose separate AuraDB resources or accept a disposable shared graph.
- [ ] Accept the bearer-link login model and define the link lifetime.
- [ ] Record an estimated class cost and an emergency stop threshold.

**Validation:** Save the permission test results, quota worksheet, AuraDB
decision, and cost estimate with the implementation review.

**Notes:** Stop before implementation if AgentCore requires attendee IAM
administration or account-wide write access. Revise the workshop flow instead.

### Phase 1: Create the Shared-Account Baseline

**Status:** Pending

**Outcome:** `environment/shared-account` contains an isolated copy of the
deployment path with clear shared-account documentation and naming.

**Checklist:**

- [ ] Copy only the required deployment files from `environment/own-account`.
- [ ] Rename defaults to identify the shared-account deployment.
- [ ] Keep `environment/own-account` behavior unchanged.
- [ ] Define stable attendee IDs with fixed-width numbering.
- [ ] Define stack names, resource names, and tags from the workshop ID and attendee ID.
- [ ] Separate shared foundation resources from per-attendee resources.
- [ ] Document the organizer profile, region, prerequisites, and expected class size.
- [ ] Document the browser link as a short-lived bearer credential.
- [ ] Document the AuraDB isolation choice and reset procedure.

**Validation:** Compare the new path with the source path. Confirm that every
change belongs to the shared-account design and that the source path still has
no changes.

**Notes:** Use one per-attendee stack when practical. This structure simplifies
replacement, token rotation, failure isolation, and cleanup.

### Phase 2: Build the IAM and Resource Boundaries

**Status:** Pending

**Outcome:** Each role grants only the actions and resources required by one
attendee workflow.

**Checklist:**

- [ ] Remove broad AWS managed read and developer policies from the instance role.
- [ ] Remove every attendee IAM create, update, attach, detach, and delete permission.
- [ ] Create a separate instance role for each attendee.
- [ ] Create separate Lambda, Gateway, CodeBuild, Runtime, and broker roles for each attendee.
- [ ] Scope the Lambda role to one secret and its own logs.
- [ ] Scope the Gateway role to two exact Lambda functions.
- [ ] Scope the CodeBuild role to one S3 prefix, one ECR repository, and its own logs.
- [ ] Scope the Runtime role to approved image sources, required models, one secret, and its own logs.
- [ ] Scope the broker role to one Runtime and one exact Runtime role pass action.
- [ ] Give the instance role exact Module 4 and Module 5 control actions.
- [ ] Give the instance role the exact CodeBuild role pass action only if live tests require it.
- [ ] Restrict the role pass condition to the CodeBuild service.
- [ ] Let the instance invoke only its own deployment broker.
- [ ] Avoid account-wide list actions when the notebooks can use known resource IDs.
- [ ] Record every unavoidable broad read action and its exposed metadata.
- [ ] Deny access paths that could modify service roles or execution configuration.
- [ ] Deny direct Runtime updates from the attendee role.
- [ ] Make the broker fix the Runtime role, network, protocol, environment, and authorization settings.

**Validation:** Run IAM policy simulation for representative allowed and denied
requests. Follow it with live tests because simulation cannot prove every
service-side condition.

**Notes:** Exact resource policies are the main protection in a shared account.
Resource name prefixes alone do not provide sufficient isolation.

### Phase 3: Harden the Browser IDE

**Status:** Pending

**Outcome:** Attendees open one browser link. The public IDE has a short
exposure window and a protected origin.

**Checklist:**

- [ ] Generate a separate high-entropy IDE token for every attendee.
- [ ] Store token values outside attendee-readable stack outputs and resources.
- [ ] Write the full links only to the organizer roster.
- [ ] Add a separate CloudFront origin secret for every attendee environment.
- [ ] Require the expected origin secret at nginx.
- [ ] Keep web ingress limited to the CloudFront origin-facing prefix list.
- [ ] Require IMDSv2 on every instance.
- [ ] Encrypt every EBS volume.
- [ ] Remove attendee sudo access.
- [ ] Block direct network access between attendee instances.
- [ ] Pin the repository to a reviewed commit or release tag.
- [ ] Lock Python dependencies and verify downloaded installers.
- [ ] Keep browser security headers enabled.
- [ ] Add a shared WAF rate rule when its cost and quota fit the event.
- [ ] Add an optional venue IP allowlist when all attendees use known networks.
- [ ] Define token rotation and lost-link procedures.
- [ ] Define automatic or scheduled expiration after the class.

**Validation:** Test the valid link, an invalid token, a missing origin header,
a direct origin request, a rotated token, and an expired environment.

**Notes:** The bearer link grants access to whoever holds it. Edge controls
protect the origin but cannot verify the attendee's identity.

### Phase 4: Provision the Module 4 Lane

**Status:** Pending

**Outcome:** Each attendee can deploy Lambda tool code and connect it to one
precreated AgentCore Gateway without creating IAM roles or Lambda functions.

**Checklist:**

- [ ] Precreate one Neo4j secret for each attendee.
- [ ] Precreate two Lambda function shells for each attendee.
- [ ] Set fixed Lambda configuration, concurrency, timeout, and logging.
- [ ] Precreate the Lambda and Gateway execution roles.
- [ ] Precreate one Gateway for each attendee.
- [ ] Precreate two placeholder Gateway targets for each attendee.
- [ ] Allow the attendee to read and update only their exact secret as required by the lab.
- [ ] Allow the attendee to update code on only their two exact Lambda functions.
- [ ] Allow the attendee to invoke and inspect only their two functions.
- [ ] Allow target inspection and updates only for their two exact targets.
- [ ] Allow invocation only through their Gateway.
- [ ] Keep function creation and configuration changes organizer-only.
- [ ] Keep Gateway creation and role changes organizer-only.
- [ ] Pass known resource IDs into the attendee environment without account-wide discovery.
- [ ] Make Module 4 reruns safe and repeatable.

**Validation:** Complete the Module 4 happy path as one attendee. Then attempt
to change another function, use another secret, update function configuration,
create a function, change the Gateway, and invoke another Gateway. Every cross-
attendee and administrative action must fail.

**Notes:** The attendee packages and deploys the tool code. The organizer
provisions the privileged scaffolding.

### Phase 5: Provision the Module 5 Lane

**Status:** Pending

**Outcome:** Each attendee builds a real container, deploys it to one precreated
AgentCore Runtime through a narrow broker, and invokes the deployed agent.

**Checklist:**

- [ ] Create one attendee build prefix in the staging bucket.
- [ ] Create one ECR repository for each attendee.
- [ ] Add a short image retention policy.
- [ ] Use one unique immutable image tag for every build.
- [ ] Create one fixed CodeBuild project for each attendee.
- [ ] Create a narrow CodeBuild service role for each attendee.
- [ ] Publish an approved placeholder image during organizer deployment.
- [ ] Create one narrow Runtime role for each attendee.
- [ ] Create one Runtime with the approved bootstrap image for each attendee.
- [ ] Create one narrow deployment broker and broker role for each attendee.
- [ ] Allow upload only to the attendee build prefix.
- [ ] Allow starts and status checks only for the attendee CodeBuild project.
- [ ] Allow image inspection only in the attendee ECR repository.
- [ ] Allow status checks and invocation only for the attendee Runtime.
- [ ] Allow the attendee to invoke only their deployment broker.
- [ ] Make the broker accept only an approved immutable image from that attendee's repository.
- [ ] Pass only the attendee secret ARN into the Runtime environment.
- [ ] Keep project, repository, and Runtime creation organizer-only.
- [ ] Block project updates and service role overrides.
- [ ] Pass known build and Runtime IDs into the attendee environment.
- [ ] Make failed builds and failed Runtime updates easy to retry.
- [ ] Add an organizer repair path that restores the bootstrap image.

**Validation:** Complete a real image build and broker deployment. Invoke the agent
and verify its logs. Attempt cross-attendee S3, ECR, CodeBuild, role pass,
Runtime, and log operations. Every cross-attendee and administrative action
must fail.

**Notes:** A participant can run arbitrary code under their own narrow build and
Runtime roles. This ability is part of the lab and remains inside their boundary.

### Phase 6: Adapt the Notebooks and Workshop Guide

**Status:** Pending

**Outcome:** The notebooks teach deployment through the safe precreated lanes
and require no attendee IAM administration.

**Checklist:**

- [ ] Remove notebook steps that create or edit IAM roles.
- [ ] Remove notebook steps that create Lambda functions, Gateways, targets, build projects, repositories, or Runtimes.
- [ ] Keep the source packaging and Lambda code update steps in Module 4.
- [ ] Keep Gateway target updates, authentication, and invocation in Module 4.
- [ ] Keep container preparation, upload, real CodeBuild execution, image verification, broker deployment, and invocation in Module 5.
- [ ] Replace the starter toolkit launch step with direct AWS API calls to exact build resources and the broker.
- [ ] Change the Runtime app to fetch its Neo4j password from its exact secret.
- [ ] Load exact attendee resource IDs from organizer-provided environment configuration.
- [ ] Show clear errors when an assigned resource is missing or belongs to another attendee.
- [ ] Make every notebook cell safe to rerun.
- [ ] Remove broad resource discovery where exact IDs are available.
- [ ] Add short explanations that separate organizer provisioning from application deployment.
- [ ] Update cleanup guidance so attendees stop work and the organizer performs account cleanup.
- [ ] Update facilitator guidance for reset, retry, and replacement procedures.

**Validation:** Run Modules 1 through 6 from a fresh attendee IDE. Confirm that
the guide matches every screen, wait state, and resource name.

**Notes:** Attendees package, build, deploy, authenticate, invoke, observe, and
debug the agent.

### Phase 7: Add Deployment, Readiness, and Cleanup Operations

**Status:** Pending

**Outcome:** One organizer can deploy the class, track readiness, distribute
links, repair one attendee, stop spending, and remove all workshop resources.

**Checklist:**

- [ ] Extend the deployment tool for a requested attendee count and reserve count.
- [ ] Run quota and permission preflight before creating stacks.
- [ ] Spread EC2 instances across available public subnets.
- [ ] Create a roster with attendee ID, stack status, and private IDE link.
- [ ] Keep roster files ignored by version control and protected on the organizer computer.
- [ ] Report bootstrap, Gateway, target, build lane, broker, and Runtime readiness.
- [ ] Add a single-attendee repair and token rotation operation.
- [ ] Add a single-attendee replacement operation.
- [ ] Add an emergency operation that stops attendee compute and builds.
- [ ] Add idempotent class cleanup.
- [ ] Empty build objects and remove ECR images before stack deletion when required.
- [ ] Keep targets and the Runtime under stack ownership for ordered cleanup.
- [ ] Delete per-attendee stacks and then shared foundation resources.
- [ ] Scan by workshop tags and name prefix for leftovers.
- [ ] Report any resource that needs manual cleanup.
- [ ] Keep the template staging bucket only when another deployment still needs it.

**Validation:** Run create, status, single-attendee repair, token rotation,
emergency stop, cleanup, and second cleanup in a test deployment. The second
cleanup must finish safely with no resources left to remove.

**Notes:** Stack deletion alone is insufficient when services retain versions,
images, objects, targets, or log groups.

### Phase 8: Run Security and Isolation Tests

**Status:** Pending

**Outcome:** Automated and live tests show that attendee workflows succeed and
cross-attendee access fails.

**Checklist:**

- [ ] Add static template validation.
- [ ] Add policy linting and IAM policy simulation.
- [ ] Add checks for wildcard resources and prohibited attendee actions.
- [ ] Add checks that every service role belongs to one attendee.
- [ ] Add checks that resource tags and names carry the correct attendee ID.
- [ ] Deploy at least two attendee environments for live isolation tests.
- [ ] Run the full positive workflow from the first environment.
- [ ] Repeat the positive workflow from the second environment.
- [ ] Test secret, Lambda, Gateway, S3, ECR, CodeBuild, log, and Runtime access across both environments.
- [ ] Test IAM administration, role pass, function configuration, project update, direct Runtime update, and Runtime creation attempts.
- [ ] Test direct origin and invalid browser token requests.
- [ ] Test malicious Lambda, build, and Runtime code against the service role boundaries.
- [ ] Record every expected denial and investigate every unexpected success.

**Validation:** Produce a pass and fail matrix for each role, action, and target
resource. Require zero unexplained cross-attendee successes.

**Notes:** Live negative tests provide the strongest evidence for this design.

### Phase 9: Pilot and Roll Out the Class

**Status:** Pending

**Outcome:** A small pilot proves timing and operations before the full class is
deployed.

**Checklist:**

- [ ] Run a two-attendee pilot with the same region and models planned for the class.
- [ ] Measure full deployment, bootstrap, build, Runtime update, and cleanup time.
- [ ] Run the notebooks with users who resemble the target audience.
- [ ] Confirm that each user needs only their browser link and workshop instructions.
- [ ] Confirm that the organizer can identify and repair one failed environment.
- [ ] Review CloudWatch, Cost Explorer, budgets, and service quota use after the pilot.
- [ ] Fix permission, timing, documentation, and cleanup issues found by the pilot.
- [ ] Freeze the reviewed repository revision and dependency lock.
- [ ] Deploy the full class plus reserve environments before the event.
- [ ] Verify every environment before sharing the roster.
- [ ] Monitor readiness, spend, builds, and Runtime health during the event.
- [ ] Rotate any exposed link immediately.
- [ ] Stop and clean up the class after the final lab.
- [ ] Run the final tagged-resource and cost scan.

**Validation:** Require a successful pilot, a complete class readiness report,
and a clean post-event resource scan.

**Notes:** Keep reserve environments unassigned until an attendee needs one.

## Completion Criteria

The shared-account deployment is complete when all of these statements are true:

- `environment/shared-account` deploys a requested number of isolated attendee environments.
- Every attendee opens the workshop through one browser link.
- No attendee environment contains the organizer's AWS credentials.
- No attendee role can administer IAM.
- No attendee role has a broad managed read or developer policy.
- Every attendee role and service role is scoped to one attendee resource set.
- Module 4 updates real Lambda code and real Gateway targets.
- Module 5 runs a real CodeBuild build and deploys it to a real AgentCore Runtime through the broker.
- Modules 1 through 6 run from a clean attendee environment.
- Positive permission tests succeed for both test attendees.
- Cross-attendee and administrative negative tests fail as expected.
- Browser origin, token rotation, and expiration tests succeed.
- Quota checks cover the full class plus reserve capacity.
- Cost alerts, retention rules, and emergency stop procedures are active.
- The organizer can repair or replace one attendee without affecting the class.
- Cleanup removes all per-attendee and shared workshop resources.
- A final tag and cost scan finds no unexplained workshop resources.
- The existing `environment/own-account` deployment remains unchanged.
