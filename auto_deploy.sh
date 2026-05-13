#!/bin/bash
# auto_deploy.sh - Automated GitHub upload script

echo "🚀 Starting automated deployment..."

# Navigate to project
cd /home/chawas/deployed/nyenje_github

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Check if there are changes
if git status --porcelain | grep -q .; then
    echo "📝 Changes detected. Adding files..."
    git add .
    
    # Commit with timestamp
    git commit -m "Auto-deploy: $TIMESTAMP"
    
    # Push to GitHub
    echo "📤 Pushing to GitHub..."
    git push origin main
    
    echo "✅ Deployment complete at $TIMESTAMP"
else
    echo "ℹ️ No changes to commit at $TIMESTAMP"
fi