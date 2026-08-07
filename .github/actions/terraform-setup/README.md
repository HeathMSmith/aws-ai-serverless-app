# Terraform Setup Composite Action

## Overview

## Overview

This composite action prepares a GitHub Actions runner to execute Terraform against AWS using GitHub OpenID Connect (OIDC) authentication.

The action performs the common initialization and quality assurance steps required before executing Terraform operations, allowing workflows to focus only on infrastructure-specific tasks such as planning, applying, or destroying infrastructure.

This action assumes the repository has already been checked out by the calling workflow.

## Features

- Configures AWS authentication using GitHub OIDC
- Installs a specified Terraform version
- Initializes the Terraform working directory
- Verifies Terraform formatting using `terraform fmt -check -recursive`
- Validates the Terraform configuration
- Designed for reuse across multiple Terraform workflows

## Inputs

| Name | Required | Description |
|------|:--------:|-------------|
| `working-directory` | Yes | Path to the Terraform root module |
| `terraform-version` | No | Terraform version to install (default: 1.15.3) |
| `aws-region` | No | AWS Region |
| `role-to-assume` | Yes | IAM role to assume using GitHub OIDC |

## Outputs

This action does not produce outputs.

## Example Usage

```yaml
steps:
  - name: Checkout Repository
    uses: actions/checkout@v4

  - name: Terraform Setup
    uses: ./.github/actions/terraform-setup
    with:
      working-directory: terraform/environments/dev
      terraform-version: "1.15.3"
      aws-region: ${{ vars.AWS_REGION }}
      role-to-assume: ${{ vars.AWS_ROLE_ARN }}

  - name: Terraform Plan
    run: terraform plan
```

## Design Philosophy

This composite action has a single responsibility: prepare a GitHub Actions runner for Terraform execution.

It centralizes AWS authentication, Terraform initialization, formatting verification, and configuration validation while intentionally leaving infrastructure operations such as **plan**, **apply**, and **destroy** to individual workflows.

Separating environment preparation from infrastructure operations reduces workflow duplication, promotes consistency, and provides a reusable foundation that can be shared across multiple Terraform projects.

## Workflow Responsibilities

This composite action is responsible for:

- Configuring AWS authentication
- Installing Terraform
- Initializing the Terraform working directory
- Enforcing Terraform formatting standards
- Validating Terraform configuration

The calling workflow remains responsible for:

- Checking out the repository
- Executing `terraform plan`
- Executing `terraform apply`
- Executing `terraform destroy`
- Handling deployment-specific logic