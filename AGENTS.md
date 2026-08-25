# Repository instructions

## Project purpose

This repository contains a serverless generative-AI web application hosted on AWS.

The primary request flow is:

1. CloudFront serves the frontend from a private S3 bucket using Origin Access Control.
2. The frontend calls an API Gateway HTTP API.
3. API Gateway invokes a Python 3.12 Lambda function.
4. Lambda calls Amazon Bedrock.
5. Successful request data is stored in DynamoDB and archived in an encrypted, versioned S3 bucket.

Preserve this architecture unless the task explicitly requests an architectural change.

## Repository layout

- `app/lambda/handler.py`: Lambda application code.
- `app/lambda/package/lambda.zip`: generated Lambda deployment artifact.
- `frontend/`: dependency-free HTML, CSS, and JavaScript frontend.
- `terraform/environments/dev/`: development Terraform root.
- `terraform/environments/prod/`: production Terraform root.
- `terraform/modules/`: shared Terraform modules.
- `.github/actions/`: reusable GitHub Actions components.
- `.github/workflows/`: plan, apply, destroy, and supporting workflows.

## Working method

Before making changes:

1. Read the request carefully.
2. Inspect `git status`.
3. Inspect the relevant source, configuration, and documentation.
4. Identify existing patterns before introducing new ones.
5. Keep changes focused on the requested outcome.

Use direct edits for small, isolated fixes.

For multi-file work or changes involving Terraform, IAM, security, CI/CD, dependencies, packaging, or architecture, present a plan before editing. If the user invokes `/plan`, do not modify files until the plan has been reviewed or the user asks implementation to begin.

Preserve unrelated user changes. Never discard, overwrite, or reformat unrelated work.

## Actions allowed by default

Within the scope of the current task, Codex may:

- Read repository files.
- Inspect Git status, history, and diffs.
- Edit relevant local files.
- Run non-destructive, offline verification commands.
- Report findings and recommend follow-up work.

## Approval required

Ask before:

- Creating or switching branches.
- Staging or committing changes.
- Installing or updating dependencies.
- Modifying dependency lockfiles.
- Regenerating or replacing `app/lambda/package/lambda.zip`.
- Running `terraform init` or `terraform plan`.
- Performing network operations.
- Accessing AWS or GitHub services.
- Deleting files or generated directories.

Never perform the following unless the user explicitly requests and confirms the exact operation:

- `terraform apply`, `terraform destroy`, imports, or state manipulation.
- AWS resource mutations.
- GitHub workflow dispatches.
- Git push, merge, rebase, reset, cherry-pick, or force operations.
- Deployment to any environment.
- Creation or submission of pull requests.
- Destructive cleanup commands.

Never expose secrets, credentials, tokens, state contents, or sensitive environment values.

## Python conventions

- Target Python 3.12.
- Prefer the standard library and existing AWS SDK dependencies.
- Do not add third-party packages without approval.
- Keep Lambda handlers small and separate parsing, validation, service calls, and response construction where practical.
- Return controlled client-facing errors; do not expose raw internal exception details.
- Do not import the Lambda handler merely to perform a syntax check because module import may initialize AWS clients or require environment variables.

For syntax verification, prefer:

`python3 -c 'import ast, pathlib; ast.parse(pathlib.Path("app/lambda/handler.py").read_text())'`

## Frontend conventions

- Preserve the existing dependency-free HTML, CSS, and JavaScript approach.
- Do not introduce a framework, package manager, or build system without approval.
- Preserve the runtime configuration mechanism.
- Avoid exposing secrets or privileged AWS configuration in frontend code.
- Verify changed JavaScript with:

`node --check frontend/app.js`

## Terraform conventions

- Preserve the separation between `dev` and `prod`.
- Preserve module boundaries unless a task requires a deliberate refactor.
- Follow the repository's configured Terraform and AWS provider versions.
- Use least-privilege IAM and preserve encryption, private S3 access, and environment isolation.
- Do not broaden IAM permissions, CORS, public access, or API exposure without explicit justification and approval.
- Do not edit Terraform state, plan files, `.terraform` contents, or provider lockfiles manually.
- Never initialize an environment automatically.

Run:

`terraform fmt -check -recursive terraform`

Run `terraform validate` only when the affected environment is already initialized. If initialization is required, stop and report that verification could not be completed without approval.

## Generated artifacts

Treat `app/lambda/package/lambda.zip` as generated output, not source code.

Do not edit or regenerate it during ordinary source changes. If a task requires updating it, first explain the proposed reproducible packaging process and obtain approval.

## Verification

Run checks appropriate to the files changed.

At minimum:

- Run `git diff --check`.
- Run the Python syntax check when Python changes.
- Run `node --check frontend/app.js` when frontend JavaScript changes.
- Run `terraform fmt -check -recursive terraform` when Terraform changes.
- Run applicable automated tests if they exist.

This repository currently may not have automated test or lint commands. Do not claim tests passed when only syntax or formatting checks were run. Clearly distinguish tests, validation, syntax checks, and checks that could not be performed.

Before finishing:

1. Review the complete diff.
2. Check `git status --short --branch`.
3. Confirm no unrelated files changed.
4. Summarize the implementation.
5. List every verification command and its result.
6. Report remaining risks or unverified behavior.

Do not commit, push, deploy, or open a pull request unless explicitly requested.
