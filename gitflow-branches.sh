#!/bin/bash

# GitFlow branch management for Google Apps Script deployments
# Creates and manages feature/develop branches with proper remote tracking

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🌿 GitFlow Branch Manager${NC}"
echo ""

# Function to create feature branch
create_feature() {
    local feature_name=$1
    if [ -z "$feature_name" ]; then
        echo -e "${RED}❌ Please provide feature name${NC}"
        echo "Usage: $0 feature <feature-name>"
        exit 1
    fi
    
    echo -e "${BLUE}🌿 Creating feature branch: feature/$feature_name${NC}"
    git checkout -b "feature/$feature_name"
    echo -e "${GREEN}✅ Feature branch created: feature/$feature_name${NC}"
    echo -e "${YELLOW}💡 To deploy: ./gitflow-deploy.sh${NC}"
    echo -e "${YELLOW}💡 To push: git push -u origin feature/$feature_name${NC}"
}

# Function to create develop branch
create_develop() {
    echo -e "${BLUE}🌿 Creating develop branch${NC}"
    git checkout -b develop
    git push -u origin develop
    echo -e "${GREEN}✅ Develop branch created and pushed${NC}"
    echo -e "${YELLOW}💡 To deploy: ./gitflow-deploy.sh${NC}"
}

# Function to merge feature to develop
merge_feature() {
    local feature_name=$1
    if [ -z "$feature_name" ]; then
        echo -e "${RED}❌ Please provide feature name${NC}"
        echo "Usage: $0 merge-feature <feature-name>"
        exit 1
    fi
    
    echo -e "${BLUE}🌿 Merging feature/$feature_name to develop${NC}"
    git checkout develop
    git merge "feature/$feature_name"
    git push origin develop
    echo -e "${GREEN}✅ Feature merged to develop${NC}"
    echo -e "${YELLOW}💡 To deploy: ./gitflow-deploy.sh${NC}"
}

# Function to merge develop to main
merge_to_main() {
    echo -e "${BLUE}🌿 Merging develop to main${NC}"
    git checkout main
    git merge develop
    git push origin main
    echo -e "${GREEN}✅ Develop merged to main${NC}"
    echo -e "${YELLOW}💡 To deploy: ./gitflow-deploy.sh${NC}"
}

# Function to show branch status
show_status() {
    echo -e "${BLUE}📊 Branch Status:${NC}"
    echo ""
    
    # Show all branches
    echo -e "${YELLOW}Local Branches:${NC}"
    git branch -vv
    
    echo ""
    echo -e "${YELLOW}Remote Branches:${NC}"
    git branch -r
    
    echo ""
    echo -e "${YELLOW}Current Branch:${NC}"
    echo -e "Branch: ${GREEN}$(git branch --show-current)${NC}"
    echo -e "Commit: ${GREEN}$(git rev-parse --short HEAD)${NC}"
    echo -e "Status: ${GREEN}$(git status --porcelain | wc -l | xargs) files changed${NC}"
}

# Main command handling
case $1 in
    "feature")
        create_feature $2
        ;;
    "develop")
        create_develop
        ;;
    "merge-feature")
        merge_feature $2
        ;;
    "merge-main")
        merge_to_main
        ;;
    "status")
        show_status
        ;;
    *)
        echo -e "${BLUE}GitFlow Branch Manager${NC}"
        echo ""
        echo "Usage:"
        echo "  $0 feature <name>     - Create feature branch"
        echo "  $0 develop           - Create develop branch"
        echo "  $0 merge-feature <name> - Merge feature to develop"
        echo "  $0 merge-main         - Merge develop to main"
        echo "  $0 status            - Show branch status"
        echo ""
        echo "Examples:"
        echo "  $0 feature player-search"
        echo "  $0 develop"
        echo "  $0 merge-feature player-search"
        echo "  $0 merge-main"
        echo "  $0 status"
        ;;
esac
