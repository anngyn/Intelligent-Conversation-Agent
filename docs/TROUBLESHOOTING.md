# Troubleshooting Guide

## Issue 1: Terraform - Container.image Contains Invalid Characters

**Error:**
```
Error: creating ECS Task Definition (agentic-system-frontend): operation error ECS: RegisterTaskDefinition, 
https response error StatusCode: 400, ClientException: Container.image contains invalid characters.

  with aws_ecs_task_definition.frontend,
  on main.tf line 635, in resource "aws_ecs_task_definition" "frontend":
  635: resource "aws_ecs_task_definition" "frontend" {
```

**Root Cause:**
Multiple issues:
1. **Wrong AWS profile** - Using `bedrock` profile (account 471112932773) but ECR repos in `default` profile (account 503130572927)
2. **ECR repos exist but Terraform doesn't know** - Manual creation or previous destroy left repos orphaned
3. **No images in ECR** - Task definition references `<account>.dkr.ecr.us-east-1.amazonaws.com/repo:latest` but image not pushed yet

**Solution:**

```bash
# 1. Switch to correct AWS profile
export AWS_PROFILE=default
aws sts get-caller-identity  # Verify correct account

# 2. Check if ECR repos exist
aws ecr describe-repositories --region us-east-1

# 3. Import existing repos into Terraform state
cd infrastructure
terraform import module.ecr.aws_ecr_repository.backend agentic-system-backend
terraform import module.ecr.aws_ecr_repository.frontend agentic-system-frontend

# 4. Build Docker images
cd ..
docker build -f backend/Dockerfile -t <ecr-url>/agentic-system-backend:latest --platform linux/amd64 .
docker build -f frontend/Dockerfile -t <ecr-url>/agentic-system-frontend:latest --platform linux/amd64 .

# 5. Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 6. Push images
docker push <ecr-url>/agentic-system-backend:latest
docker push <ecr-url>/agentic-system-frontend:latest

# 7. Apply Terraform
cd infrastructure
terraform apply
```

**Prevention:**
Always deploy in this order:
1. Create ECR repos (`terraform apply -target=module.ecr`)
2. Build + push images
3. Apply full infrastructure

---

## Issue 2: Bedrock ValidationException - Conversation Must Start with User Message

**Error:**
```
ValidationException: A conversation must start with a user message. Try again with a conversation that starts with a user message.
```

**Root Cause:**
DynamoDB stored messages with identical timestamps when written in same batch → undefined sort order → sometimes loaded as `[AIMessage, HumanMessage]` → Bedrock rejected.

**Files Affected:**
- `backend/app/storage/conversation.py:180`

**Fix:**
```python
# Before: All messages got same timestamp
created_at = int(time.time() * 1000)

# After: Strictly increasing timestamps
base_timestamp = int(time.time() * 1000)
for index, message in enumerate(normalized_messages):
    created_at = base_timestamp + index  # Guarantees ordering
```

**Secondary Issue:**
Memory summarization used `AIMessage` for summary prefix → if triggered, history started with AI message.

**Fix:** `backend/app/agent/memory.py:84`
```python
# Before: new_messages = [AIMessage(content=summary_text), *recent_messages]
# After:  new_messages = [HumanMessage(content=summary_text), *recent_messages]
```

**Clear Bad Data:**
```bash
# Delete messages with duplicate timestamps
aws dynamodb delete-item --table-name agentic-system-conversation-history \
  --key '{"session_id":{"S":"<session-id>"},"message_key":{"S":"<timestamp>#<uuid>"}}'
```

---

## Issue 3: RDS Order Lookup Always Returns "Not Found"

**Symptoms:**
- Backend logs show `order_store_initialized` but no `order_store_seeded`
- Order lookups fail with `not_found` even for valid test data
- No seeding errors in logs

**Root Cause:**
Docker image missing `dataset/mock/orders.json` → `seed_from_json()` failed silently → empty database.

**Files Affected:**
- `backend/Dockerfile:22` - Only copied `dataset/processed/` (FAISS), not `dataset/mock/`

**Fix:**
```dockerfile
# Before:
COPY dataset/processed/ ./dataset/processed/

# After:
COPY dataset/processed/ ./dataset/processed/
COPY dataset/mock/ ./dataset/mock/
```

**Enable Seeding:**
`infrastructure/templates/backend-container-definitions.json.tftpl`:
```json
{
  "name": "ORDER_SEED_ON_STARTUP",
  "value": "true"
}
```

**Verify Seeding:**
```bash
aws logs filter-log-events --log-group-name /ecs/agentic-system/backend \
  --filter-pattern "order_store_seeded" --max-items 1
```

Should see:
```json
{"message": "order_store_seeded", "backend": "postgres", "records": 3}
```

**Test Data:**
After seeding:
- Name: `John Smith`, SSN: `1234`, DOB: `1990-01-15` → Order `ORD-98765`, status `Shipped`
- Name: `Jane Doe`, SSN: `5678`, DOB: `1985-06-20` → Order `ORD-87654`, status `Delivered`
- Name: `Michael Johnson`, SSN: `9012`, DOB: `1992-11-03` → Order `ORD-76543`, status `Processing`

---

## Issue 4: Session History Disappears on Page Reload

**Behavior:**
User reloads frontend page → conversation history lost.

**Cause:**
Session ID stored in Streamlit's `st.session_state` (browser memory) → each page load generates new UUID → fresh session.

**This Is Expected:**
Current implementation = stateless demo. Each page load = new conversation.

**DynamoDB Still Has History:**
Old conversations stored in `agentic-system-conversation-history` table. Just need UI to access them.

**Production Solutions:**
1. **URL-based sessions:** `/chat?session=abc-123`
2. **Cookie persistence:** Store session_id in browser cookie
3. **Session list UI:** Show user's past sessions to resume

---

## Issue 5: GitHub Actions CD Workflow - Terraform Backend Not Found

**Error:**
```
Error: Backend initialization required: Run "terraform init"
```

**Root Cause:**
Terraform backend commented out → local state file not committed to Git → CI can't access existing infrastructure state.

**Solution:**

**1. Create S3 backend:**
```bash
# S3 bucket for state storage
aws s3 mb s3://terraform-state-agentic-system-<account-id> --region us-east-1
aws s3api put-bucket-versioning --bucket terraform-state-agentic-system-<account-id> \
  --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket terraform-state-agentic-system-<account-id> \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-lock-agentic-system \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

**2. Configure backend in `infrastructure/providers.tf`:**
```hcl
backend "s3" {
  bucket         = "terraform-state-agentic-system-<account-id>"
  key            = "agentic-system/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "terraform-lock-agentic-system"
  encrypt        = true
}
```

**3. Migrate local state:**
```bash
cd infrastructure
terraform init -migrate-state
# Answer "yes" when prompted
```

**4. Update GitHub Actions IAM role permissions:**
Add S3 + DynamoDB permissions to role policy (see `github-actions-permissions.json`).

**Verify:**
```bash
aws s3 ls s3://terraform-state-agentic-system-<account-id>/agentic-system/
# Should see: terraform.tfstate
```

**Benefits:**
- CI/CD can access shared state
- State versioning enabled (rollback capability)
- State locking prevents concurrent modifications
- Encrypted at rest

---

## Deployment Flow

After code fixes:
```bash
# 1. Rebuild Docker image
docker build -f backend/Dockerfile -t <ecr-url>:latest --platform linux/amd64 .

# 2. Push to ECR
export AWS_PROFILE=default
docker push <ecr-url>:latest

# 3. Force ECS redeploy
aws ecs update-service --cluster agentic-system-cluster \
  --service agentic-system-backend-service --force-new-deployment

# 4. Wait 2-3 min for new task to start + pass health checks

# 5. Check logs
aws logs tail /ecs/agentic-system/backend --since 5m --follow
```

---

## Debug Commands

**Check AWS profile/account:**
```bash
aws sts get-caller-identity
aws configure list-profiles
```

**Check DynamoDB message order:**
```bash
aws dynamodb scan --table-name agentic-system-conversation-history \
  --max-items 10 --query 'Items[*].[message_key.S, message_type.S]'
```

**Check ECS task environment variables:**
```bash
aws ecs describe-task-definition --task-definition agentic-system-backend \
  --query 'taskDefinition.containerDefinitions[0].environment'
```

**Check backend logs for errors:**
```bash
aws logs filter-log-events --log-group-name /ecs/agentic-system/backend \
  --filter-pattern "ERROR" --max-items 20
```

**Check if images exist in ECR:**
```bash
aws ecr list-images --repository-name agentic-system-backend
aws ecr list-images --repository-name agentic-system-frontend
```

**Force new ECS deployment:**
```bash
aws ecs update-service --cluster agentic-system-cluster \
  --service agentic-system-backend-service --force-new-deployment
```
