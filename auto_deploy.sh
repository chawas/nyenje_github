#!/bin/bash
# auto_deploy.sh - Enhanced automated GitHub upload script

echo "🚀 Starting automated deployment at $(date)"

# Navigate to project
cd /home/chawas/deployed/nyenje_github || exit 1

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Check Git status
echo "📊 Checking Git status..."
git status

# Check for any changes (including untracked files)
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "📝 Changes detected. Adding files..."
    
    # Add all changes including new files
    git add -A
    
    # Show what's being committed
    echo "📋 Files to be committed:"
    git status --short
    
    # Commit with timestamp
    git commit -m "Auto-deploy: $TIMESTAMP"
    
    # Show commit details
    echo "📦 Commit created:"
    git log -1 --oneline
    
    # Push to GitHub
    echo "📤 Pushing to GitHub..."
    
    # Try push with verbose output
    if git push -u origin main 2>&1; then
        echo "✅ Deployment complete at $TIMESTAMP"
    else
        echo "❌ Push failed. Trying force push? (use with caution)"
        # Uncomment next line only if you're sure
        # git push -u origin main --force
    fi
else
    echo "ℹ️ No changes to commit at $TIMESTAMP"
    
    # Check if there are unpushed commits
    UNPUSHED=$(git log origin/main..main --oneline)
    if [ -n "$UNPUSHED" ]; then
        echo "📤 Found unpushed commits. Pushing..."
        git push origin main
    else
        echo "✅ Everything is up to date with origin/main"
    fi
fi

echo "🎉 Done at $(date)"