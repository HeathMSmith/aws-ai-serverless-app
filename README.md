# AI Serverless Application (AWS + Terraform)

## Overview

This project implements a production-style, serverless AI application on AWS using Terraform. It demonstrates secure frontend delivery, scalable backend processing, and cost-conscious design using fully managed services.

The application accepts user input via a web interface, processes it using AWS Bedrock, stores results in DynamoDB, and returns a response to the user.

This repository is structured to reflect real-world cloud engineering practices, including multi-environment deployments, CI/CD automation, and secure infrastructure design.

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

## Key Design Decisions (The "Why")

### CloudFront + OAC (Security + Performance)
CloudFront enforces HTTPS, improves global latency, and ensures S3 remains private.

### Serverless Backend (Cost + Scalability)
Lambda + API Gateway scale automatically and eliminate idle cost.

### DynamoDB (On-Demand)
Removes capacity planning and scales automatically.

### Bedrock Integration
Provides AI capabilities without managing models.

### Multi-Environment Architecture
Separates dev and prod with isolated domains and resources.

### Terraform
Ensures reproducibility and modular infrastructure design.

### CI/CD with OIDC
Removes need for static credentials and secures deployments.

---

## Deployment

### Dev

```
cd terraform/environments/dev
terraform init
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

### Prod

```
cd terraform/environments/prod
terraform init
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

---

## Teardown

```
terraform destroy
```

---

## Cost Considerations

- Serverless = minimal cost
- Destroy environments when not in use

---

## Security Considerations

- Private S3 (OAC)
- IAM least privilege
- HTTPS enforced

---

## Author

Heath Smith

Testing
