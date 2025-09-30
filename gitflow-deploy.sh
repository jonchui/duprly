#!/bin/bash

# GitFlow-style deployment script for Google Apps Script
# Deploys based on branch status and remote tracking

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get current branch info
CURRENT_BRANCH=$(git branch --show-current)
GIT_COMMIT=$(git rev-parse --short HEAD)
GIT_MESSAGE=$(git log -1 --pretty=format:"%s")

# Check if branch is pushed to remote
IS_PUSHED=$(git branch -r | grep "origin/$CURRENT_BRANCH" || echo "")

echo -e "${BLUE}🌿 GitFlow Deployment Check${NC}"
echo -e "📝 Current Branch: ${YELLOW}$CURRENT_BRANCH${NC}"
echo -e "📝 Git Commit: ${YELLOW}$GIT_COMMIT${NC}"
echo -e "📝 Git Message: ${YELLOW}$GIT_MESSAGE${NC}"
echo ""

# Determine deployment strategy based on branch
case $CURRENT_BRANCH in
  "main"|"master")
    if [ -n "$IS_PUSHED" ]; then
      echo -e "${GREEN}✅ PRODUCTION DEPLOYMENT${NC}"
      echo -e "Branch $CURRENT_BRANCH is pushed to remote - deploying to production"
      
      # Push code
      echo -e "${BLUE}📤 Pushing to Google Apps Script...${NC}"
      clasp push --force
      
      # Create production version
      echo -e "${BLUE}🏷️  Creating production version...${NC}"
      clasp version "PROD: $GIT_COMMIT - $GIT_MESSAGE"
      
      # Create production deployment
      echo -e "${BLUE}🚀 Creating production deployment...${NC}"
      clasp deploy --description "PRODUCTION: $GIT_COMMIT - $GIT_MESSAGE"
      
      echo -e "${GREEN}✅ Production deployment complete!${NC}"
    else
      echo -e "${RED}❌ CANNOT DEPLOY TO PRODUCTION${NC}"
      echo -e "Branch $CURRENT_BRANCH is not pushed to remote"
      echo -e "Run: ${YELLOW}git push origin $CURRENT_BRANCH${NC} first"
      exit 1
    fi
    ;;
    
  "develop"|"dev")
    if [ -n "$IS_PUSHED" ]; then
      echo -e "${YELLOW}🔧 STAGING DEPLOYMENT${NC}"
      echo -e "Branch $CURRENT_BRANCH is pushed to remote - deploying to staging"
      
      # Push code
      echo -e "${BLUE}📤 Pushing to Google Apps Script...${NC}"
      clasp push --force
      
      # Create staging version
      echo -e "${BLUE}🏷️  Creating staging version...${NC}"
      clasp version "STAGING: $GIT_COMMIT - $GIT_MESSAGE"
      
      # Create staging deployment
      echo -e "${BLUE}🚀 Creating staging deployment...${NC}"
      clasp deploy --description "STAGING: $GIT_COMMIT - $GIT_MESSAGE"
      
      echo -e "${YELLOW}✅ Staging deployment complete!${NC}"
    else
      echo -e "${RED}❌ CANNOT DEPLOY TO STAGING${NC}"
      echo -e "Branch $CURRENT_BRANCH is not pushed to remote"
      echo -e "Run: ${YELLOW}git push origin $CURRENT_BRANCH${NC} first"
      exit 1
    fi
    ;;
    
  feature/*|bugfix/*|hotfix/*)
    echo -e "${BLUE}🧪 FEATURE DEPLOYMENT${NC}"
    echo -e "Feature branch detected - creating development deployment"
    
    # Push code (no remote check for features)
    echo -e "${BLUE}📤 Pushing to Google Apps Script...${NC}"
    clasp push --force
    
    # Create feature version
    echo -e "${BLUE}🏷️  Creating feature version...${NC}"
    clasp version "FEATURE: $GIT_COMMIT - $GIT_MESSAGE"
    
    # Create feature deployment
    echo -e "${BLUE}🚀 Creating feature deployment...${NC}"
    clasp deploy --description "FEATURE: $GIT_COMMIT - $GIT_MESSAGE"
    
    echo -e "${BLUE}✅ Feature deployment complete!${NC}"
    ;;
    
  *)
    echo -e "${YELLOW}⚠️  UNKNOWN BRANCH TYPE${NC}"
    echo -e "Branch $CURRENT_BRANCH doesn't match GitFlow conventions"
    echo -e "Deploying as development branch..."
    
    # Push code
    echo -e "${BLUE}📤 Pushing to Google Apps Script...${NC}"
    clasp push --force
    
    # Create dev version
    echo -e "${BLUE}🏷️  Creating development version...${NC}"
    clasp version "DEV: $GIT_COMMIT - $GIT_MESSAGE"
    
    # Create dev deployment
    echo -e "${BLUE}🚀 Creating development deployment...${NC}"
    clasp deploy --description "DEV: $GIT_COMMIT - $GIT_MESSAGE"
    
    echo -e "${YELLOW}✅ Development deployment complete!${NC}"
    ;;
esac

echo ""
echo -e "${BLUE}📊 Deployment Summary:${NC}"
echo -e "Branch: ${YELLOW}$CURRENT_BRANCH${NC}"
echo -e "Commit: ${YELLOW}$GIT_COMMIT${NC}"
echo -e "Pushed to Remote: ${GREEN}$([ -n "$IS_PUSHED" ] && echo "YES" || echo "NO")${NC}"
echo ""
echo -e "🔗 View deployments: ${YELLOW}clasp deployments${NC}"
echo -e "🔗 View versions: ${YELLOW}clasp versions${NC}"
