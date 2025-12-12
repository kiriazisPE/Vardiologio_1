# Environment Secrets and Configuration Guide

This document explains how to configure environment variables and secrets for the Shift Planner application.

## 📋 Overview

The application uses environment variables for configuration to follow the [12-factor app](https://12factor.net/) methodology. This separates configuration from code and allows the same codebase to run in different environments.

## 🔑 Required Secrets

### Development Environment

Create a `.env` file in the `shift_planner/` directory:

```bash
# AI/LLM Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here

# Application Settings
APP_ENV=development
DEBUG=true
AUTH_ENABLED=false

# Database (SQLite for development)
DB_PATH=shift_maker.sqlite3

# Optional: Logging
LOG_LEVEL=INFO
```

### Production Environment

**⚠️ Never commit production secrets to version control!**

Production secrets should be configured in your deployment platform or CI/CD system.

## 🌍 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes* | - | OpenAI API key for AI scheduling (*if using DSPy features) |
| `APP_ENV` | No | `production` | Environment name: `development`, `staging`, `production` |
| `DEBUG` | No | `false` | Enable debug mode (never use in production) |
| `AUTH_ENABLED` | No | `true` | Enable authentication system |
| `DB_PATH` | No | `shift_maker.sqlite3` | Path to SQLite database file |
| `LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `PORT` | No | `8501` | Port for Streamlit application |
| `HEALTH_CHECK_PORT` | No | `8001` | Port for health check endpoint |

## 🔧 Configuration by Environment

### Local Development

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env`** with your values:
   ```bash
   OPENAI_API_KEY=sk-your-api-key
   APP_ENV=development
   DEBUG=true
   AUTH_ENABLED=false
   ```

3. **Never commit `.env`** - it's already in `.gitignore`

### GitHub Actions (CI/CD)

Configure secrets in GitHub repository settings:

**Path**: Repository → Settings → Secrets and variables → Actions

#### Required Secrets for CI:
- `OPENAI_API_KEY` - For running DSPy integration tests

#### Required Secrets for CD:
- `OPENAI_API_KEY` - Production API key
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions

**Adding a secret**:
1. Go to repository Settings
2. Click "Secrets and variables" → "Actions"
3. Click "New repository secret"
4. Name: `OPENAI_API_KEY`
5. Value: Your production API key
6. Click "Add secret"

### Docker Container

Pass environment variables to Docker containers:

```bash
# Using -e flag
docker run -p 8501:8501 \
  -e OPENAI_API_KEY="sk-your-key" \
  -e APP_ENV="production" \
  -e AUTH_ENABLED="true" \
  ghcr.io/kiriazispe/vardiologio_1:latest

# Using --env-file
docker run -p 8501:8501 \
  --env-file .env.production \
  ghcr.io/kiriazispe/vardiologio_1:latest
```

### Docker Compose

Create environment-specific files:

**.env.production**:
```bash
OPENAI_API_KEY=sk-prod-key
APP_ENV=production
DEBUG=false
AUTH_ENABLED=true
DB_PATH=/data/shift_maker.sqlite3
```

**docker-compose.yml**:
```yaml
services:
  app:
    image: ghcr.io/kiriazispe/vardiologio_1:latest
    env_file:
      - .env.production
    environment:
      - PORT=8501
    ports:
      - "8501:8501"
```

### Cloud Platforms

#### AWS ECS/Fargate
- Use AWS Secrets Manager or Parameter Store
- Reference secrets in task definition
- [AWS Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data.html)

#### Google Cloud Run
```bash
gcloud run deploy shift-planner \
  --image=ghcr.io/kiriazispe/vardiologio_1:latest \
  --set-env-vars="APP_ENV=production" \
  --set-secrets="OPENAI_API_KEY=openai-key:latest"
```

#### Azure Container Instances
```bash
az container create \
  --resource-group myResourceGroup \
  --name shift-planner \
  --image ghcr.io/kiriazispe/vardiologio_1:latest \
  --environment-variables \
    'APP_ENV'='production' \
  --secure-environment-variables \
    'OPENAI_API_KEY'='sk-your-key'
```

#### DigitalOcean App Platform
- Add environment variables in App Platform dashboard
- Mark sensitive variables as "encrypted"

## 🔐 Authentication Configuration

The app uses Streamlit Authenticator with bcrypt hashed passwords.

### Setup Authentication

1. **Create auth configuration file**:
   ```bash
   cp shift_planner/.streamlit/auth.yaml.example shift_planner/.streamlit/auth.yaml
   ```

2. **Generate password hashes**:
   ```python
   import bcrypt
   
   password = "your_secure_password"
   hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
   print(hashed.decode('utf-8'))
   ```

3. **Update auth.yaml** with hashed passwords (never plain text!)

4. **Security note**: 
   - `auth.yaml` is in `.gitignore` - never commit it
   - Only `auth.yaml.example` should be in version control
   - Use different passwords for each environment

## 📝 Best Practices

### ✅ DO:
- Use different API keys for development and production
- Rotate secrets regularly
- Use strong, unique passwords
- Store production secrets in secure vaults
- Use environment variables for all configuration
- Document all required variables

### ❌ DON'T:
- Commit secrets to version control
- Share API keys in chat/email
- Use the same secrets across environments
- Store secrets in code or comments
- Use weak or default passwords
- Expose secrets in logs or error messages

## 🔍 Verifying Configuration

### Check Environment Variables
```python
import os

# In Python shell or script
print(f"API Key set: {bool(os.getenv('OPENAI_API_KEY'))}")
print(f"Environment: {os.getenv('APP_ENV', 'not set')}")
```

### Test Application
```bash
# Run health check
curl http://localhost:8001/health

# Should return:
# {"status":"healthy","service":"shift-planner","version":"dev"}
```

## 🆘 Troubleshooting

### "API key not set" error
- Check `.env` file exists in `shift_planner/` directory
- Verify `OPENAI_API_KEY` is set correctly
- For Docker: ensure environment variable is passed to container

### Authentication not working
- Verify `auth.yaml` exists and has correct format
- Check password hashes are valid bcrypt hashes
- Ensure `AUTH_ENABLED=true` if using authentication

### Database errors
- Check `DB_PATH` points to valid location
- Ensure directory has write permissions
- For Docker: verify volume is mounted correctly

## 📚 Additional Resources

- [12-Factor App Config](https://12factor.net/config)
- [OpenAI API Keys](https://platform.openai.com/api-keys)
- [bcrypt Password Hashing](https://pypi.org/project/bcrypt/)
- [Docker Environment Variables](https://docs.docker.com/compose/environment-variables/)

---

**Security Note**: If you accidentally commit secrets, immediately:
1. Revoke/rotate the exposed secrets
2. Remove from git history using `git filter-repo` or BFG
3. Contact GitHub support to purge from their caches
