#!/bin/bash

# Deploy Google Apps Script with Git commit tracking
# Usage: ./deploy-with-git.sh "Your deployment description"

set -e

# Get git info
GIT_COMMIT=$(git rev-parse --short HEAD)
GIT_MESSAGE=$(git log -1 --pretty=format:"%s")
BRANCH=$(git branch --show-current)

# Default description or use provided argument
DESCRIPTION=${1:-"Deployment from $BRANCH"}

echo "🚀 Deploying Google Apps Script..."
echo "📝 Git Commit: $GIT_COMMIT"
echo "📝 Git Message: $GIT_MESSAGE"
echo "🌿 Branch: $BRANCH"
echo "📋 Description: $DESCRIPTION"
echo ""

# Push latest code
echo "📤 Pushing code to Google Apps Script..."
clasp push --force

# Create version with git info
echo "🏷️  Creating version with git info..."
clasp version "Git: $GIT_COMMIT - $DESCRIPTION"

# Create deployment with git info
echo "🚀 Creating deployment with git info..."
clasp deploy --description "Git: $GIT_COMMIT - $DESCRIPTION"

echo ""
echo "✅ Deployment complete!"
echo "🔗 View deployments: clasp deployments"
echo "🔗 View versions: clasp versions"
