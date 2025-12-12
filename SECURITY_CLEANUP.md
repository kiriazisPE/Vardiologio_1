# Purging Sensitive Data from Git History

## ⚠️ CRITICAL SECURITY ISSUE

The file `shift_planner/.streamlit/auth.yaml` was committed with plaintext passwords in comments:
- admin123
- manager123
- user123

These passwords are now in the git history and need to be completely removed.

## 🛠️ Solution Options

### Option 1: BFG Repo-Cleaner (Recommended - Easiest)

1. **Install BFG**:
   ```bash
   # Windows (using Chocolatey)
   choco install bfg-repo-cleaner
   
   # Or download from: https://rtyley.github.io/bfg-repo-cleaner/
   ```

2. **Create fresh clone**:
   ```bash
   git clone --mirror https://github.com/kiriazisPE/Vardiologio_1.git
   cd Vardiologio_1.git
   ```

3. **Run BFG to remove the file**:
   ```bash
   bfg --delete-files auth.yaml
   ```

4. **Clean up and force push**:
   ```bash
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   git push --force
   ```

### Option 2: git-filter-repo (Advanced)

1. **Install git-filter-repo**:
   ```bash
   pip install git-filter-repo
   ```

2. **Run filter**:
   ```bash
   git filter-repo --path shift_planner/.streamlit/auth.yaml --invert-paths
   ```

3. **Force push**:
   ```bash
   git push origin --force --all
   git push origin --force --tags
   ```

### Option 3: GitHub Support (Nuclear Option)

If the above doesn't work or passwords are cached by GitHub:

1. Go to: https://support.github.com/contact
2. Select "Remove sensitive data"
3. Provide:
   - Repository: kiriazisPE/Vardiologio_1
   - File: shift_planner/.streamlit/auth.yaml
   - Commits: All commits containing the file
   - Reason: Exposed passwords

## ⚠️ IMPORTANT: Before Running

1. **Notify all collaborators** - they'll need to re-clone
2. **Backup your repository** - these operations are destructive
3. **Close all open PRs** - they'll need to be recreated
4. **Change the passwords immediately** - assume they're compromised

## 📋 Post-Cleanup Checklist

- [ ] Verify file is removed from history: `git log --all --full-history -- "**/auth.yaml"`
- [ ] Generate new bcrypt password hashes
- [ ] Update local `auth.yaml` with new passwords
- [ ] Test authentication with new passwords
- [ ] Force all users to re-authenticate
- [ ] Monitor for suspicious activity

## 🔒 Preventing Future Incidents

Already implemented:
- ✅ `.streamlit/auth.yaml` in `.gitignore`
- ✅ `auth.yaml.example` template without real credentials
- ✅ GitHub secret scanning enabled
- ✅ Pre-commit hooks recommended in CONTRIBUTING.md

## 📝 Manual Steps for Now

Until you run the cleanup:

1. **Change passwords immediately**:
   ```python
   import bcrypt
   
   # Generate new hashes
   passwords = ['new_admin_pass', 'new_manager_pass', 'new_user_pass']
   for pwd in passwords:
       hashed = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt())
       print(f"{pwd}: {hashed.decode('utf-8')}")
   ```

2. **Update local auth.yaml** with new hashes

3. **Invalidate old sessions** - users will need to re-login

---

**Status**: Passwords are still accessible in git history at:
- Commit: eaeaa72 (and earlier)
- File: shift_planner/.streamlit/auth.yaml

**Action Required**: Run cleanup script ASAP
