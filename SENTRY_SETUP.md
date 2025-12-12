# Sentry Setup Guide

## Step 1: Create Sentry Account

1. Go to https://sentry.io/signup/
2. Sign up (free tier includes 5,000 errors/month)
3. Create a new organization (e.g., "Shift Planner")

## Step 2: Create Project

1. Click "Create Project"
2. Select platform: **Python**
3. Set alert frequency: "Alert me on every new issue"
4. Project name: **shift-planner**
5. Click "Create Project"

## Step 3: Get DSN

After creating the project, you'll see:

```
SENTRY_DSN=https://[PUBLIC_KEY]@[ORG_ID].ingest.sentry.io/[PROJECT_ID]
```

**Save this DSN** - you'll need it for deployment!

## Step 4: Local Testing (Optional)

Test Sentry integration locally:

```bash
# Set environment variables
$env:SENTRY_ENABLED="true"
$env:SENTRY_DSN="your-dsn-here"
$env:APP_ENV="development"

# Run the app
cd shift_planner
streamlit run main.py
```

## Step 5: Test Error Tracking

Add this temporary code to test:

```python
# In main.py, add after imports:
from monitoring import init_sentry, capture_exception

init_sentry()

# Test error
try:
    1 / 0
except Exception as e:
    capture_exception(e)
```

Check your Sentry dashboard - you should see the error!

## Step 6: Production Configuration

### For DigitalOcean:
```bash
# Add as encrypted environment variable in App Platform:
SENTRY_DSN=https://[YOUR_DSN]
SENTRY_ENABLED=true
APP_ENV=production
```

### For Fly.io:
```bash
fly secrets set SENTRY_DSN=https://[YOUR_DSN]
fly secrets set SENTRY_ENABLED=true
```

### For Google Cloud Run:
```bash
gcloud run services update shift-planner \
  --set-secrets="SENTRY_DSN=sentry-dsn:latest" \
  --set-env-vars="SENTRY_ENABLED=true"
```

## Step 7: Configure Alerts

In Sentry dashboard:

1. Go to **Settings** → **Alerts**
2. Create alert rule:
   - **Trigger**: "When error count is above 10 in 1 hour"
   - **Action**: Email notification
3. Save rule

## Step 8: Performance Monitoring (Optional)

Enable performance tracking:

```python
# Already configured in monitoring.py!
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of transactions
```

## Features You'll Get

✅ **Error Tracking**
- Automatic exception capture
- Stack traces with context
- User information (if authenticated)
- Environment details

✅ **Performance Monitoring**
- Transaction tracking
- Database query performance
- API call timing

✅ **Breadcrumbs**
- User actions before errors
- Navigation history
- API calls

✅ **Release Tracking**
- Track which version has errors
- Compare error rates between releases

## Integration Points

The monitoring is already integrated at:

- `monitoring.py` - Main Sentry configuration
- `logging_config.py` - Logs errors to Sentry
- Ready to use in `main.py`

## Dashboard Overview

After deployment, your Sentry dashboard will show:

- **Issues**: All unique errors
- **Performance**: Transaction timing
- **Releases**: Version comparison
- **Alerts**: Email notifications

## Cost

- **Free tier**: 5,000 errors/month
- **Team plan** ($26/month): 50,000 errors/month
- **Business plan** ($80/month): 150,000 errors/month

For a small app, free tier is usually sufficient!

## Next Steps

1. ✅ Create Sentry account
2. ✅ Get DSN
3. ✅ Add to deployment configuration
4. ✅ Deploy and monitor!

---

**Your Sentry DSN will look like:**
```
https://abc123def456@o123456.ingest.sentry.io/7890123
```

**Save it securely** and add it to your deployment platform!
