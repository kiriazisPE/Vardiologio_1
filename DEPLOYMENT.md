# 🚀 Streamlit Cloud Deployment Guide

This guide will help you deploy Shift Plus Pro to Streamlit Cloud for free hosting.

## Prerequisites

- GitHub account
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- Basic familiarity with GitHub

## Step-by-Step Deployment

### 1. Prepare Your Repository

1. **Fork this repository** to your GitHub account:
   - Click the "Fork" button on the repository page
   - This creates your own copy of the code

2. **Clone your fork locally** (optional, for customization):
   ```bash
   git clone https://github.com/YOUR_USERNAME/shift-plus-pro.git
   cd shift-plus-pro
   ```

### 2. Deploy to Streamlit Cloud

1. **Visit Streamlit Cloud**: Go to [share.streamlit.io](https://share.streamlit.io/)

2. **Connect GitHub**: 
   - Click "New app"
   - Connect your GitHub account if not already connected

3. **Configure Deployment**:
   - **Repository**: Select your forked repository
   - **Branch**: `main` (or `master`)
   - **Main file path**: `shift_plus.py`
   - **App URL**: Choose a custom URL (optional)

4. **Click "Deploy"**: The initial deployment will start

### 3. Configure Secrets

1. **Access App Settings**:
   - After deployment, go to your app dashboard
   - Click the gear icon (⚙️) next to your app name
   - Select "Secrets"

2. **Add API Keys**:
   ```toml
   AI_API_KEY = "sk-proj-your-actual-openai-api-key-here"
   OPENAI_API_KEY = "sk-proj-your-actual-openai-api-key-here"
   ```

3. **Save Changes**: Click "Save" to apply the secrets

### 4. Verify Deployment

1. **Check App Status**: Your app should show "Running" status
2. **Test Features**:
   - Visit your live app URL
   - Try generating a schedule to verify AI integration
   - Check that all features work properly

## Common Issues & Solutions

### ❌ "No module named 'xyz'"
- **Solution**: Add missing packages to `requirements.txt`
- **Fix**: Update requirements.txt and redeploy

### ❌ "OpenAI API key not found"
- **Solution**: Check secrets configuration
- **Fix**: Ensure API key is correctly set in Streamlit secrets

### ❌ App won't start
- **Solution**: Check logs in Streamlit Cloud dashboard
- **Fix**: Review error messages and fix code issues

### ❌ Database errors
- **Solution**: SQLite works automatically on Streamlit Cloud
- **Fix**: No additional configuration needed

## Customization Tips

### Update App Title
Edit `shift_plus.py`:
```python
st.set_page_config(
    page_title="Your Company Scheduler",
    page_icon="🏢"
)
```

### Custom Styling
Add to `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
```

### Environment-Specific Settings
Use `st.secrets` for different configurations:
```python
if st.secrets.get("ENVIRONMENT") == "production":
    # Production settings
else:
    # Development settings
```

## Post-Deployment

### Share Your App
- Copy the app URL from Streamlit Cloud dashboard
- Share with your team or customers
- Add the URL to your repository README

### Monitor Usage
- Check Streamlit Cloud analytics
- Monitor app performance
- Review logs for any issues

### Updates & Maintenance
- Push changes to your GitHub repository
- Streamlit Cloud auto-deploys from your main branch
- Test changes in a separate branch first

## Support

Need help? 
- 📖 [Streamlit Documentation](https://docs.streamlit.io/)
- 💬 [Streamlit Community](https://discuss.streamlit.io/)
- 🐛 Create an issue in this repository

---

**🎉 Congratulations! Your app is now live on the internet!**