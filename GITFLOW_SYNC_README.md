# GitFlow Sync for DUPR Club Manager

This setup provides automatic synchronization between your GitHub repository and Google Apps Script (clasp) using Git hooks and GitHub Actions.

## 🎯 What's Included

### **Git Hooks**
- **`pre-push`** - Validates clasp setup before pushing to GitHub
- **`post-commit`** - Optional auto-sync after local commits
- **`post-receive`** - Auto-sync after successful GitHub push

### **GitHub Actions**
- **`.github/workflows/deploy-to-clasp.yml`** - Automatic deployment on push to main/master

### **Helper Scripts**
- **`sync-to-clasp.sh`** - Manual sync script
- **`.dupr-sync-config`** - Configuration file

## 🚀 Setup Instructions

### **1. GitHub Secrets (Required for GitHub Actions)**

Add these secrets to your GitHub repository:

1. Go to **Settings > Secrets and variables > Actions**
2. Add new repository secret:
   - **Name**: `CLASP_TOKEN`
   - **Value**: Your clasp authentication token

**To get your clasp token:**
```bash
clasp login
# Copy the token from ~/.clasprc.json
```

### **2. Enable Auto-Sync (Optional)**

```bash
# Enable auto-sync after commits
export DUPR_AUTO_SYNC=1

# Or edit .dupr-sync-config
nano .dupr-sync-config
```

### **3. Test the Setup**

```bash
# Test pre-push validation
git push origin main

# Test manual sync
./sync-to-clasp.sh "Test deployment"

# Test GitHub Actions
git push origin main  # Should trigger automatic deployment
```

## 🔄 How It Works

### **Local Development Workflow**

1. **Make changes** to `apps-script/Code.js`
2. **Commit changes**: `git commit -m "Update DUPR search logic"`
3. **Pre-push hook** validates clasp setup
4. **Push to GitHub**: `git push origin main`
5. **Post-receive hook** automatically syncs to Google Apps Script
6. **GitHub Actions** creates a new version with commit message

### **Automatic Deployment**

When you push to `main` or `master`:

1. **GitHub Actions** triggers automatically
2. **Authenticates** with Google using `CLASP_TOKEN`
3. **Pushes** changes to Google Apps Script
4. **Creates version** with commit message
5. **Notifies** deployment status

### **Manual Deployment**

```bash
# Quick sync
./sync-to-clasp.sh

# Sync with custom message
./sync-to-clasp.sh "Fixed authentication bug"

# Direct clasp commands
clasp push
clasp version "Manual update"
```

## 📋 Configuration

### **Environment Variables**

```bash
# Auto-sync settings
export DUPR_AUTO_SYNC=1              # Enable auto-sync
export DUPR_VERSION_PREFIX="PROD"    # Version prefix
export DUPR_SYNC_BRANCHES="main"     # Branches to sync
```

### **Configuration File**

Edit `.dupr-sync-config`:

```bash
DUPR_AUTO_SYNC_ON_COMMIT=0    # Auto-sync after commits
DUPR_AUTO_SYNC_ON_PUSH=1      # Auto-sync after pushes
DUPR_VERSION_PREFIX="PROD"    # Version prefix
DUPR_SYNC_BRANCHES="main"     # Branches to sync
```

## 🛠️ Troubleshooting

### **Common Issues**

**"clasp not authenticated"**
```bash
clasp login
```

**"clasp not found"**
```bash
npm install -g @google/clasp
```

**"GitHub Actions failing"**
- Check `CLASP_TOKEN` secret is set correctly
- Verify `.clasp.json` exists
- Check `apps-script/Code.js` is not empty

**"Hooks not executing"**
```bash
# Make hooks executable
chmod +x .git/hooks/*
```

### **Debug Mode**

```bash
# Enable debug output
export DUPR_DEBUG=1
git push origin main
```

## 📊 Version Management

### **Automatic Versions**

Versions are automatically created with:
- **Format**: `PRODUCTION: abc1234 - Commit message`
- **Trigger**: Every push to main/master
- **Description**: Git commit message

### **Manual Versions**

```bash
# Create version with custom message
clasp version "Fixed critical bug in player search"

# List all versions
clasp versions

# Deploy specific version
clasp deploy --versionNumber 5
```

## 🔒 Security

### **Authentication**

- **Local**: Uses `~/.clasprc.json` (created by `clasp login`)
- **GitHub Actions**: Uses `CLASP_TOKEN` secret
- **No passwords** stored in repository

### **Permissions**

- **Read-only**: Hooks only push to Google Apps Script
- **No destructive**: Never deletes or modifies GitHub repo
- **Audit trail**: All deployments logged with commit messages

## 🎉 Benefits

- **🔄 Automatic**: No manual sync required
- **📝 Tracked**: Every deployment linked to Git commit
- **🛡️ Safe**: Pre-push validation prevents broken deployments
- **⚡ Fast**: Only syncs when `apps-script/` files change
- **🔍 Transparent**: Clear logging and error messages

---

**Happy coding with GitFlow! 🚀**
