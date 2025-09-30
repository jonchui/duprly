#!/bin/bash
# Setup script for pre-commit hooks

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔧 DUPR Club Manager - Pre-Commit Hook Setup${NC}"
echo "=============================================="
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Not in a git repository${NC}"
    exit 1
fi

echo "Available pre-commit hooks:"
echo "1. ${GREEN}Standard${NC} - Basic diff review with validation"
echo "2. ${GREEN}Interactive${NC} - Detailed review with better formatting"
echo "3. ${GREEN}Disable${NC} - Remove pre-commit hook"
echo ""

read -p "Choose option (1-3): " choice

case $choice in
    1)
        echo -e "${BLUE}📋 Setting up standard pre-commit hook...${NC}"
        cp .git/hooks/pre-commit .git/hooks/pre-commit.backup 2>/dev/null || true
        echo -e "${GREEN}✅ Standard pre-commit hook activated${NC}"
        ;;
    2)
        echo -e "${BLUE}📋 Setting up interactive pre-commit hook...${NC}"
        cp .git/hooks/pre-commit .git/hooks/pre-commit.backup 2>/dev/null || true
        cp .git/hooks/pre-commit-interactive .git/hooks/pre-commit
        echo -e "${GREEN}✅ Interactive pre-commit hook activated${NC}"
        ;;
    3)
        echo -e "${YELLOW}⚠️  Disabling pre-commit hook...${NC}"
        mv .git/hooks/pre-commit .git/hooks/pre-commit.disabled 2>/dev/null || true
        echo -e "${GREEN}✅ Pre-commit hook disabled${NC}"
        ;;
    *)
        echo -e "${RED}❌ Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}🎯 What the pre-commit hook does:${NC}"
echo "• Shows colored diff (green additions, red deletions)"
echo "• Validates Google Apps Script syntax"
echo "• Checks for placeholder credentials"
echo "• Shows commit summary"
echo "• Prevents commits with issues"
echo ""
echo -e "${GREEN}💡 Tip: Run 'git commit --no-verify' to skip the hook${NC}"
