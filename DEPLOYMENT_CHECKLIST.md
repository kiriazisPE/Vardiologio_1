# 🚀 Deployment Checklist

## ✅ Pre-Deployment (COMPLETED)

- [x] Git history cleaned (passwords purged)
- [x] New secure passwords generated
- [x] CI/CD pipeline working
- [x] Docker images building successfully
- [x] Documentation complete
- [x] Monitoring infrastructure ready

## 📋 Ready to Deploy

### Option 1: DigitalOcean App Platform (Recommended - Easiest)

**Cost**: ~$12-27/month

1. **Create DigitalOcean Account**
   - Sign up at: https://cloud.digitalocean.com
   - Add payment method

2. **Deploy Using App Spec**
   ```bash
   # Install doctl
   brew install doctl  # macOS
   # or download: https://docs.digitalocean.com/reference/doctl/
   
   # Authenticate
   doctl auth init
   
   # Create app
   doctl apps create --spec .do/app.yaml
   ```

3. **Configure Secrets in Dashboard**
   - Go to App Platform → Settings → Environment Variables
   - Add (encrypted):
     - `OPENAI_API_KEY` = your OpenAI API key
     - `SENTRY_DSN` = your Sentry DSN (optional)
   - Save and redeploy

4. **Add Database (Optional)**
   - Uncomment database section in `.do/app.yaml`
   - Update app: `doctl apps update YOUR_APP_ID --spec .do/app.yaml`

5. **Access Your App**
   - URL will be: https://shift-planner-xxxxx.ondigitalocean.app
   - Can add custom domain later

### Option 2: Fly.io (Cost-Effective)

**Cost**: ~$0-15/month (can scale to zero)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Launch app
cd shift_planner
fly launch --no-deploy

# Set secrets
fly secrets set OPENAI_API_KEY=sk-your-key
fly secrets set SENTRY_DSN=https://your-dsn

# Deploy
fly deploy
```

### Option 3: Google Cloud Run (Serverless)

**Cost**: Pay per use (~$5-20/month)

```bash
# Build and deploy
gcloud run deploy shift-planner \
  --source=./shift_planner \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="APP_ENV=production" \
  --set-secrets="OPENAI_API_KEY=openai-key:latest"
```

## 🔐 Required Environment Variables

### Minimum Required:
```bash
OPENAI_API_KEY=sk-your-openai-key-here
APP_ENV=production
```

### Recommended:
```bash
SENTRY_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn
DATABASE_URL=postgresql://user:pass@host:5432/db  # If using PostgreSQL
AUTH_ENABLED=true
LOG_LEVEL=INFO
```

## 📊 Post-Deployment Checklist

After deployment:

- [ ] Verify app is accessible
- [ ] Test login with new passwords:
  - Admin: `f@moCSxGb[/fWs7{"RCG`
  - Manager: `7{Pk*nl|rUTg]RIP,{#T`
  - User: `]q[<l!8qt>YQ_mot>UT.`
- [ ] Check health endpoint: `https://your-app.com/_stcore/health`
- [ ] Verify Sentry is receiving events (check dashboard)
- [ ] Test AI scheduling features
- [ ] Set up custom domain (optional)
- [ ] Configure SSL certificate (automatic on most platforms)
- [ ] Set up database backups
- [ ] Configure alerts in Sentry

## 🔄 Continuous Deployment

Already configured! Every push to `main` will:

1. ✅ Run tests
2. ✅ Build Docker image
3. ✅ Push to GitHub Container Registry
4. 🔜 Deploy automatically (when enabled in CD pipeline)

## 💰 Cost Estimates

| Platform | Starter | With Database | Notes |
|----------|---------|---------------|-------|
| **DigitalOcean** | $12 | $27 | Simplest, fixed pricing |
| **Fly.io** | $0-5 | $10-15 | Scales to zero, global |
| **Cloud Run** | $5-10 | $15-25 | Pay per use, Google infra |
| **AWS Fargate** | $20-30 | $40-60 | Enterprise, more complex |

## 📝 Next Steps After Deployment

1. **Monitor Performance**
   - Watch Sentry for errors
   - Check response times
   - Monitor resource usage

2. **Optimize**
   - Add caching if needed
   - Optimize database queries
   - Fine-tune auto-scaling

3. **Scale**
   - Add more instances if needed
   - Upgrade database tier
   - Add CDN for static assets

4. **Maintain**
   - Regular security updates
   - Dependency updates (Dependabot enabled)
   - Monitor costs

## 🆘 Troubleshooting

### App won't start
- Check environment variables are set
- View logs: `doctl apps logs` or `fly logs`
- Verify DATABASE_URL if using PostgreSQL

### High costs
- Reduce instance count
- Use auto-scaling/scale-to-zero
- Optimize Docker image size

### Slow performance
- Add database indexes
- Enable caching
- Upgrade instance size

## 📚 Documentation

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Detailed platform guides
- [SECRETS_SETUP.md](SECRETS_SETUP.md) - Environment configuration
- [SENTRY_SETUP.md](SENTRY_SETUP.md) - Monitoring setup
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development workflow

---

## 🎉 You're Ready to Deploy!

**Recommended first deployment**: DigitalOcean App Platform (easiest)

Just run:
```bash
doctl auth init
doctl apps create --spec .do/app.yaml
```

Then configure secrets in the web dashboard!
