# Next Steps Before Submission

This checklist helps you complete the remaining tasks before submitting your assignment.

## ✅ Completed

- [x] Full Level 100 + 200 implementation
- [x] Code is committed to git
- [x] Comprehensive documentation (README, SETUP, ARCHITECTURE, SUBMISSION_SUMMARY)
- [x] Test suite with pytest
- [x] GitHub Actions CI/CD workflows
- [x] Terraform infrastructure code
- [x] Docker and docker-compose setup

## 🔲 Required Before Submission

### 1. Test Locally

```bash
# Install dependencies
cd backend
pip install -e ".[dev]"

# Build FAISS index (CRITICAL - won't work without this)
python scripts/ingest_pdf.py

# Test backend
pytest -v

# Run backend
python -m app.main
```

In another terminal:
```bash
# Run frontend
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

**Test these scenarios:**
- Ask a 10-K question: "What were Amazon's total net sales in 2019?"
- Check order status with: John Smith, 1234, 1990-01-15
- Verify streaming works (tokens appear one by one)
- Test multi-turn conversation (agent remembers context)

### 2. Record Demo Video (Optional but Recommended)

**Suggested structure (3-5 minutes):**

1. **Intro (30 seconds)**
   - "Hi, I'm [Name], and this is my submission for the Cloud Kinetics SA Intern assignment"
   - "I've built a conversational agent with RAG and secure tool-based workflows"

2. **RAG Demo (90 seconds)**
   - Show Streamlit UI
   - Ask: "What were Amazon's total revenues?"
   - Show streaming response with source citations
   - Ask follow-up: "What were the main business segments?"
   - Show that agent maintains context

3. **Order Status Demo (90 seconds)**
   - Say: "I want to check my order status"
   - Show multi-turn identity verification
   - Provide John Smith / 1234 / 1990-01-15
   - Show order details with streaming

4. **Architecture Overview (60 seconds)**
   - Show `docs/ARCHITECTURE.md` diagram
   - Mention: "LangChain ReAct agent, AWS Bedrock Claude, FAISS vector store"
   - Show `infrastructure/main.tf`: "Complete Terraform for ECS Fargate deployment"
   - Show `.github/workflows/`: "CI/CD with GitHub Actions"

5. **Wrap-up (30 seconds)**
   - "Total cost: ~$20/month when running"
   - "I'm excited to discuss design decisions and Level 300 extensions in the interview"

**Recording options:**
- Loom (free, easy)
- OBS Studio (open source)
- Zoom (record to local)

### 3. Push to GitHub

```bash
# Create GitHub repository (if not done)
# https://github.com/new

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Push
git push -u origin main
```

### 4. AWS Deployment (Optional)

If you want to show a live deployment:

```bash
# Prerequisites:
# - AWS account with Bedrock access
# - AWS CLI configured
# - Terraform installed

cd infrastructure
terraform init
terraform plan
terraform apply

# Get ALB URL
terraform output alb_dns_name
```

**IMPORTANT**: This will incur costs (~$20/month). To avoid charges:
- Scale ECS service to 0: `aws ecs update-service --cluster agentic-system-cluster --service agentic-system-service --desired-count 0`
- Or destroy: `terraform destroy`

### 5. Finalize Submission Document

Edit `docs/SUBMISSION_SUMMARY.md` and fill in:
- Your name
- Your email
- GitHub repository URL
- Demo video link (if recorded)

## 📧 Submission Checklist

Send to Cloud Kinetics:

- [ ] **GitHub Repository URL**: https://github.com/YOUR_USERNAME/YOUR_REPO
- [ ] **README.md**: Clear intro, setup instructions, architecture
- [ ] **Demo Video** (optional but recommended): Link to Loom/YouTube
- [ ] **Submission Email**: Include:
  - Link to repository
  - Brief summary (3-4 sentences): "I completed Level 100 + 200, implementing a RAG-based conversational agent with LangChain and AWS Bedrock, deployed via Terraform to ECS Fargate with CI/CD."
  - Any questions or clarifications

## 🔍 Pre-Submission Checklist

Before sending, verify:

- [ ] README has no placeholder text (e.g., "[Your Name]")
- [ ] All tests pass: `pytest -v`
- [ ] Linter is clean: `ruff check .`
- [ ] `.gitignore` excludes `dataset/processed/` and `.env`
- [ ] No AWS credentials or secrets in code
- [ ] GitHub Actions workflows are valid YAML
- [ ] Terraform validates: `terraform validate`
- [ ] Docker images build: `docker build -t test ./backend`

## 💡 Interview Prep

Be ready to discuss:

1. **Design Decisions**
   - Why FAISS over OpenSearch? (Cost: $0 vs $700/mo)
   - Why Haiku over Sonnet? (10x cheaper, sufficient for task)
   - Why ECS Fargate? (No cold starts, easy streaming)

2. **Trade-offs**
   - In-memory sessions: Simple but not persistent
   - Single NAT Gateway: Cost vs high availability
   - Baked FAISS index: Fast startup vs dynamic updates

3. **Level 300 Extensions**
   - How would you design the conversation history schema?
   - What observability would you add? (LangSmith, X-Ray, CloudWatch dashboards)
   - How would you evaluate RAG quality? (RAGAS, human eval)

4. **Scalability**
   - What happens at 1000 concurrent users? (ECS auto-scaling, DynamoDB sessions)
   - How would you handle 1M documents? (OpenSearch, document preprocessing pipeline)

## 📚 Reference Docs

During interview, you can reference:
- `docs/ARCHITECTURE.md` - System diagrams and flows
- `docs/SUBMISSION_SUMMARY.md` - Design decisions
- `CLAUDE.md` - Commands and structure
- `infrastructure/main.tf` - AWS resources

## ⏰ Time Management

If you're short on time, prioritize:

1. ✅ **CRITICAL**: Test locally (backend + frontend work)
2. ✅ **HIGH**: Push to GitHub with clear README
3. ⚠️ **MEDIUM**: Record demo video
4. ⚠️ **LOW**: Deploy to AWS (can demo locally)

Good luck! 🚀
