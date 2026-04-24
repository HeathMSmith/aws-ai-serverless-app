# AI Serverless Application (AWS + Terraform)

## Overview

This project implements a production-style, serverless AI application on AWS using Terraform. It demonstrates secure frontend delivery, scalable backend processing, and cost-conscious design using fully managed services.

The system accepts user input via a web interface, processes it using AWS Bedrock, stores results in DynamoDB, and returns a response to the user.

---

## Live Demo

- **Production:** https://ai.hmsdev.click  
- **Development:** https://ai-dev.hmsdev.click  

> Note: Infrastructure is deployed on-demand and may be temporarily unavailable to minimize cost.

---

## Architecture

```
User
 ↓
CloudFront (HTTPS + CDN)
 ↓
S3 (Private Origin via OAC)
 ↓
Frontend (Static Web App)
 ↓
API Gateway
 ↓
Lambda (Python 3.12)
 ↓
Bedrock (AI Processing)
 ↓
DynamoDB (Persistence)
```

---

## Key Design Decisions

### 1. CloudFront + Origin Access Control (OAC)
- S3 bucket is **not publicly accessible**
- CloudFront acts as the only entry point
- Enforces HTTPS and improves performance globally

### 2. Serverless Backend
- API Gateway + Lambda eliminate idle compute cost
- Automatically scales with demand
- No infrastructure management required

### 3. DynamoDB (On-Demand)
- No capacity planning required
- Cost-efficient for low to moderate usage
- Integrated with KMS for encryption

### 4. Bedrock Integration
- Enables AI-driven response generation
- Abstracts model hosting and scaling
- Keeps architecture lightweight

### 5. Multi-Environment Design
- Separate **dev** and **prod** environments
- Environment-specific domains:
  - `ai-dev.hmsdev.click`
  - `ai.hmsdev.click`
- Isolated resources per environment

### 6. Infrastructure as Code (Terraform)
- Fully reproducible deployments
- Modular structure (frontend, backend, API)
- Remote state with locking

### 7. CI/CD with GitHub Actions (OIDC)
- No long-lived AWS credentials
- Secure role assumption via OpenID Connect
- Automated:
  - Terraform plan/apply
  - CloudFront cache invalidation

### 8. CloudFront Cache Invalidation
- Triggered after each deployment
- Ensures users always receive the latest frontend assets
- Eliminates stale content issues

---

## Repository Structure

```
terraform/
  modules/
    frontend/
    lambda/
    apigateway/
    dynamodb/
    s3/
  environments/
    dev/
    prod/

frontend/
  index.html
  app.js
  assets/
```

---

## Deployment


### Prerequisites

- AWS account
- Terraform installed
- GitHub repository with Actions enabled

---
> Note: Terraform plans are generated and applied as separate steps to ensure deterministic and reviewable infrastructure changes.

### Deploy (Dev)

```
cd terraform/environments/dev
terraform init
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

---

### Deploy (Prod)

```
cd terraform/environments/prod
terraform init
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

---

### Destroy (Cost Control)

```
terraform destroy
```

Or via GitHub Actions:

- Run **Terraform Destroy (Controlled)**
- Provide:
  - environment: `dev` or `prod`
  - confirm: `destroy`

---

## Cost Considerations

This project is designed to operate within AWS Free Tier or near-zero cost under light usage.

| Service        | Cost Behavior |
|----------------|--------------|
| Lambda         | Pay per request |
| API Gateway    | Low cost for small traffic |
| DynamoDB       | On-demand billing |
| CloudFront     | Free tier eligible |
| S3             | Minimal storage cost |

> Recommendation: Destroy environments when not in use.

---

## Security Considerations

- S3 bucket is private (OAC enforced)
- IAM roles follow least-privilege principles
- No hardcoded credentials (OIDC used in CI/CD)
- Data encrypted via AWS KMS
- HTTPS enforced via CloudFront + ACM

---

## Observability

- CloudWatch Logs for Lambda execution
- API Gateway metrics available
- Structured logging implemented in Lambda

---

## Future Improvements

- User authentication (Amazon Cognito)
- WAF integration for rate limiting and protection
- Enhanced observability (CloudWatch dashboards)
- Request history UI backed by DynamoDB
- Cache-busting strategy for frontend assets

---

## What This Project Demonstrates

- Designing secure, scalable serverless architectures
- Implementing multi-environment infrastructure with Terraform
- Integrating AI services into cloud-native applications
- Building CI/CD pipelines with GitHub Actions and OIDC
- Managing cost through serverless and on-demand services

---

## Author

Heath Smith  
AWS Certified Solutions Architect – Associate
