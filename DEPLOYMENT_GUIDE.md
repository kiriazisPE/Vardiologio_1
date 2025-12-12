# Deployment Guide - Cloud Platforms

Complete guide for deploying Shift Planner to various cloud platforms.

## 🎯 Platform Recommendations

### Quick Comparison

| Platform | Difficulty | Cost/Month | Best For |
|----------|-----------|------------|----------|
| **DigitalOcean App Platform** | ⭐ Easy | $12-25 | Quick deployment, beginners |
| **Fly.io** | ⭐⭐ Medium | $0-15 | Cost-effective, global |
| **Google Cloud Run** | ⭐⭐ Medium | Pay-per-use | Auto-scaling, serverless |
| **AWS ECS/Fargate** | ⭐⭐⭐ Hard | $30+ | Enterprise, full control |
| **Azure Container Instances** | ⭐⭐ Medium | $20+ | Microsoft ecosystem |

---

## 1️⃣ DigitalOcean App Platform (Recommended for Beginners)

### Prerequisites
- DigitalOcean account
- GitHub repository connected

### Deployment Steps

1. **Create App**:
   ```bash
   # Using doctl CLI
   doctl apps create --spec .do/app.yaml
   
   # Or use web UI: https://cloud.digitalocean.com/apps
   ```

2. **Configure Environment Variables**:
   - `OPENAI_API_KEY` - Your OpenAI API key (encrypted)
   - `APP_ENV` - `production`
   - `DATABASE_URL` - PostgreSQL connection string
   - `SENTRY_DSN` - Sentry project DSN (optional)

3. **Database Setup**:
   - Create Managed PostgreSQL database
   - Database will be automatically linked
   - Connection string in `${db.DATABASE_URL}`

### App Spec (.do/app.yaml)

```yaml
name: shift-planner
region: nyc
services:
  - name: web
    github:
      repo: kiriazisPE/Vardiologio_1
      branch: main
      deploy_on_push: true
    source_dir: /shift_planner
    dockerfile_path: shift_planner/Dockerfile
    
    health_check:
      http_path: /health
      initial_delay_seconds: 20
      period_seconds: 10
      timeout_seconds: 5
      success_threshold: 1
      failure_threshold: 3
    
    http_port: 8501
    instance_count: 1
    instance_size_slug: basic-xxs  # $12/month
    
    envs:
      - key: APP_ENV
        value: production
      - key: OPENAI_API_KEY
        scope: RUN_TIME
        type: SECRET
      - key: SENTRY_ENABLED
        value: "true"
      - key: SENTRY_DSN
        scope: RUN_TIME
        type: SECRET
    
databases:
  - name: shift-planner-db
    engine: PG
    version: "15"
    size: db-s-1vcpu-1gb  # $15/month
```

### Deploy Command
```bash
# Install doctl
brew install doctl  # macOS
# or download from: https://docs.digitalocean.com/reference/doctl/

# Authenticate
doctl auth init

# Create app
doctl apps create --spec .do/app.yaml

# Update app
doctl apps update YOUR_APP_ID --spec .do/app.yaml
```

---

## 2️⃣ Fly.io (Cost-Effective, Global)

### Prerequisites
- Fly.io account
- Flyctl CLI installed

### Setup

1. **Install flyctl**:
   ```bash
   # macOS
   brew install flyctl
   
   # Windows
   pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"
   
   # Linux
   curl -L https://fly.io/install.sh | sh
   ```

2. **Initialize app**:
   ```bash
   cd shift_planner
   fly launch --no-deploy
   ```

3. **Configure secrets**:
   ```bash
   fly secrets set OPENAI_API_KEY=sk-your-key
   fly secrets set DATABASE_URL=postgresql://...
   fly secrets set SENTRY_DSN=https://...
   ```

4. **Create PostgreSQL database**:
   ```bash
   fly postgres create --name shift-planner-db
   fly postgres attach --app shift-planner shift-planner-db
   ```

5. **Deploy**:
   ```bash
   fly deploy
   ```

### fly.toml Configuration

```toml
app = "shift-planner"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  APP_ENV = "production"
  PORT = "8501"

[http_service]
  internal_port = 8501
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0  # Scale to zero when idle
  
  [[http_service.checks]]
    grace_period = "10s"
    interval = "30s"
    method = "GET"
    timeout = "5s"
    path = "/_stcore/health"

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

---

## 3️⃣ Google Cloud Run

### Prerequisites
- Google Cloud account
- gcloud CLI installed

### Deployment

1. **Build and push image**:
   ```bash
   # Set project
   gcloud config set project YOUR_PROJECT_ID
   
   # Build image
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/shift-planner
   ```

2. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy shift-planner \
     --image gcr.io/YOUR_PROJECT_ID/shift-planner \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars="APP_ENV=production" \
     --set-secrets="OPENAI_API_KEY=openai-key:latest,DATABASE_URL=database-url:latest" \
     --max-instances=10 \
     --memory=1Gi \
     --cpu=1 \
     --port=8501
   ```

3. **Create Cloud SQL PostgreSQL**:
   ```bash
   gcloud sql instances create shift-planner-db \
     --database-version=POSTGRES_15 \
     --tier=db-f1-micro \
     --region=us-central1
   
   gcloud sql databases create shiftplanner \
     --instance=shift-planner-db
   ```

### Terraform Configuration

```hcl
resource "google_cloud_run_service" "shift_planner" {
  name     = "shift-planner"
  location = "us-central1"

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/shift-planner:latest"
        
        ports {
          container_port = 8501
        }
        
        env {
          name  = "APP_ENV"
          value = "production"
        }
        
        env {
          name = "OPENAI_API_KEY"
          value_from {
            secret_key_ref {
              name = "openai-api-key"
              key  = "latest"
            }
          }
        }
      }
    }
  }
}
```

---

## 4️⃣ AWS ECS/Fargate

### Prerequisites
- AWS account
- AWS CLI configured
- ECR repository created

### Deployment

1. **Push to ECR**:
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
   
   # Tag and push
   docker tag shift-planner:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/shift-planner:latest
   docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/shift-planner:latest
   ```

2. **Create task definition** (task-definition.json):
   ```json
   {
     "family": "shift-planner",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "512",
     "memory": "1024",
     "containerDefinitions": [
       {
         "name": "shift-planner",
         "image": "YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/shift-planner:latest",
         "portMappings": [
           {
             "containerPort": 8501,
             "protocol": "tcp"
           }
         ],
         "environment": [
           {"name": "APP_ENV", "value": "production"}
         ],
         "secrets": [
           {
             "name": "OPENAI_API_KEY",
             "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:openai-key"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/shift-planner",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "ecs"
           }
         }
       }
     ]
   }
   ```

3. **Create service**:
   ```bash
   aws ecs create-service \
     --cluster shift-planner-cluster \
     --service-name shift-planner \
     --task-definition shift-planner \
     --desired-count 1 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
   ```

---

## 🔐 Secrets Management

### GitHub Secrets (for CI/CD)
```bash
# Add secrets via GitHub CLI
gh secret set OPENAI_API_KEY --body "sk-your-key"
gh secret set DATABASE_URL --body "postgresql://..."
gh secret set SENTRY_DSN --body "https://..."
```

### Platform-Specific Secrets
- **DigitalOcean**: App Platform → Settings → Environment Variables (encrypted)
- **Fly.io**: `fly secrets set KEY=value`
- **GCP**: Secret Manager → `gcloud secrets create`
- **AWS**: Secrets Manager or Parameter Store

---

## 📊 Post-Deployment Checklist

- [ ] Verify application is accessible
- [ ] Test health endpoints (`/health`, `/ready`)
- [ ] Confirm database connectivity
- [ ] Check error tracking (Sentry dashboard)
- [ ] Test authentication
- [ ] Verify environment variables loaded correctly
- [ ] Set up custom domain (optional)
- [ ] Configure SSL/TLS certificates
- [ ] Set up monitoring alerts
- [ ] Test auto-scaling (if configured)

---

## 🆘 Troubleshooting

### Application won't start
- Check logs: `docker logs`, `fly logs`, `gcloud run logs`
- Verify all environment variables are set
- Ensure DATABASE_URL is correct
- Check health check endpoint responds

### Database connection issues
- Verify DATABASE_URL format
- Check firewall/security group rules
- Ensure database is in same region/VPC
- Test connection locally first

### High costs
- Enable auto-scaling to zero (Fly.io, Cloud Run)
- Use spot/preemptible instances
- Optimize Docker image size
- Set resource limits

---

For detailed platform documentation:
- [DigitalOcean App Platform](https://docs.digitalocean.com/products/app-platform/)
- [Fly.io](https://fly.io/docs/)
- [Google Cloud Run](https://cloud.google.com/run/docs)
- [AWS ECS](https://docs.aws.amazon.com/ecs/)
