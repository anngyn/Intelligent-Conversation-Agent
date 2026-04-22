# Cloud Kinetics Assignment - Submission Summary

**Candidate**: `Nguyen An`  
**Date**: April 22, 2026  
**Position**: SA AI/Data Intern

## Executive Summary

This submission delivers:
- Level 100 core agent capability
- Level 200 AWS deployment and CI/CD
- Level 300 baseline for data persistence and observability

System solves two business flows:
- grounded document Q&A through RAG
- secure order status lookup through identity-verified tool use

## What Was Built

### 1. Grounded document Q&A
- Amazon 10-K processed into FAISS vector index
- Bedrock Titan Embed v2 for embeddings
- Bedrock Claude 3 Haiku for reasoning and answer generation
- retrieved context used to ground answers and reduce hallucination

### 2. Secure order lookup workflow
- multi-turn identity verification
- requires full name, last 4 SSN digits, and date of birth before order lookup
- tool path validates identity fields before returning order information

### 3. Conversation memory
- conversation history persisted in DynamoDB
- supports ordered session replay by `session_id`
- suitable for multi-instance ECS runtime

### 4. Operational customer and order data
- PostgreSQL-backed data model for customers, orders, and order items
- relational structure used for integrity and indexed lookup
- better fit than key-value storage for operational business data

### 5. AWS deployment
- Terraform-managed AWS infrastructure
- ECS deployment split into frontend and backend services
- ALB in front of frontend
- private backend service
- ECR repositories
- CloudWatch monitoring

### 6. Observability baseline
- structured JSON logging
- PII redaction
- EMF custom metrics
- CloudWatch dashboard
- CloudWatch alarms

## Architecture Summary

### Runtime flow
`User -> ALB -> frontend ECS service -> backend ECS service -> Bedrock`

### Storage split

| Data type | Store | Why |
|---|---|---|
| Conversation history | DynamoDB | Session-based append and ordered read |
| Customer and order operations | PostgreSQL | Relational integrity and indexed lookup |
| Vector retrieval corpus | FAISS | Small corpus, lowest cost floor |

### Production-aware vector decision
- current implementation: FAISS
- optional next step: OpenSearch
- reason not implemented now: cost floor too high for assignment-scale corpus

## Key Design Decisions

### DynamoDB for conversation history
- structure matches chat access pattern directly
- partition by session, ordered message retrieval
- low idle cost
- scales naturally with concurrent chat sessions

### PostgreSQL for customer and order operations
- customer-to-order-to-item relationships are relational
- identity verification benefits from normalized data and indexing
- stronger fit than DynamoDB for operational records

### FAISS for vector retrieval
- current corpus small
- lowest cost
- simplest implementation
- clear migration path to OpenSearch if corpus size or filtering requirements grow

### ECS Fargate for runtime
- better fit for always-on streaming frontend/backend services than Lambda
- simpler deployment story for this application shape

## Level Coverage

### Level 100
- agent with tool use
- RAG retrieval
- conversation handling
- streaming responses

### Level 200
- Terraform infrastructure
- ECS deployment
- CI/CD pipeline
- AWS networking and IAM

### Level 300 baseline
- DynamoDB-backed conversation persistence
- PostgreSQL-backed operational data
- structured logs, metrics, dashboard, alarms

## Validation Status

### Verified locally
- targeted backend tests pass
- `terraform validate` passes

### Verified artifacts
- AWS architecture diagram updated
- demo script updated
- presentation guide updated

### Not yet fully verified in AWS
- full `terraform apply` smoke test in a real AWS account
- GitHub Actions end-to-end deployment run

## Cost and Scale Positioning

Current design is intentionally right-sized:
- managed AWS services where they clearly fit
- FAISS where managed vector search would be premature
- storage split by access pattern instead of forcing one database for all data

Scale path:
- DynamoDB scales conversation throughput
- PostgreSQL scales operational data path
- ECS scales frontend and backend horizontally
- OpenSearch remains optional future step for larger retrieval workloads

## Security Positioning

- identity verification enforced before order lookup
- PII redaction in logs
- private backend service
- IAM least privilege
- explicit separation between retrieval data, session state, and operational customer/order data

## Deliverables Included

- source code
- Terraform infrastructure
- GitHub Actions workflows
- technical documentation
- architecture diagram
- demo script
- presentation guide

## Final Submission Checklist

- [x] Codebase updated to current architecture
- [x] README updated to current architecture
- [x] Submission summary updated to current architecture
- [x] Design decision docs aligned with implementation
- [x] Demo script aligned with implementation
- [ ] Fill candidate name
- [ ] Add repository link
- [ ] Add demo video link
- [ ] Run final demo recording
- [ ] Optional: run one AWS deployment smoke test

## Recommended Reviewer Message

`Main architecture decision was to separate conversation state, operational business data, and retrieval data by access pattern, then keep current implementation cost-aware while preserving a clear path to production scale.`

## Links To Use In Review

- [README](/D:/An/Project/Assignment/README.md:1)
- [Design Decisions](/D:/An/Project/Assignment/docs/DESIGN_DECISIONS.md:1)
- [Data Design](/D:/An/Project/Assignment/docs/DATA_DESIGN.md:1)
- [Observability Design](/D:/An/Project/Assignment/docs/OBSERVABILITY_DESIGN.md:1)
- [Demo Script](/D:/An/Project/Assignment/docs/DEMO_SCRIPT.md:1)
- [Presentation Guide](/D:/An/Project/Assignment/docs/PRESENTATION.md:1)
- [AWS Architecture Diagram](/D:/An/Project/Assignment/docs/system-architecture-aws.drawio)

## Submission Metadata

**Candidate**: `<fill before submission>`  
**Repository Link**: `<fill before submission>`  
**Demo Video Link**: `<fill before submission>`
