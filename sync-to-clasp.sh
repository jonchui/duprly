#!/bin/bash
# Manual sync script for DUPR Club Manager
# Usage: ./sync-to-clasp.sh [version-description]

set -e

echo "🔄 Syncing DUPR Club Manager to Google Apps Script..."

# Check if clasp is available
if ! command -v clasp &> /dev/null; then
    echo "❌ Error: clasp not found. Install with: npm install -g @google/clasp"
    exit 1
fi

# Check if authenticated
if ! clasp list > /dev/null 2>&1; then
    echo "❌ Error: clasp not authenticated. Run 'clasp login' first."
    exit 1
fi

# Push to Google Apps Script
echo "📤 Pushing to Google Apps Script..."
if clasp push; then
    echo "✅ Successfully pushed to Google Apps Script!"
    
    # Create version
    if [ -n "$1" ]; then
        version_desc="$1"
    else
        commit_msg=$(git log --format=%s -n 1 HEAD 2>/dev/null || echo "Manual sync")
        version_desc="Manual sync: $(date '+%Y-%m-%d %H:%M')"
    fi
    
    echo "📝 Creating version: $version_desc"
    clasp version "$version_desc"
    
    echo "🎉 Sync complete!"
else
    echo "❌ Failed to push to Google Apps Script"
    exit 1
fi
