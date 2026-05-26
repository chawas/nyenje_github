#!/usr/bin/env python3
"""
GitHub Auto-Updater for Nyenje Bay Tool
Automates git add, commit, and push with smart features
"""

import os
import subprocess
import sys
from datetime import datetime
import argparse
import glob

class GitHubUpdater:
    def __init__(self, repo_path=None):
        """Initialize the updater with repository path"""
        if repo_path is None:
            self.repo_path = os.getcwd()
        else:
            self.repo_path = repo_path
        
        self.changed_files = []
        self.untracked_files = []
        
    def run_command(self, command, capture_output=True):
        """Run a shell command and return output"""
        try:
            if capture_output:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True
                )
                return result.stdout.strip(), result.stderr.strip(), result.returncode
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=self.repo_path
                )
                return "", "", result.returncode
        except Exception as e:
            return "", str(e), 1
    
    def check_git_installed(self):
        """Check if git is installed"""
        stdout, stderr, code = self.run_command("git --version")
        if code != 0:
            print("❌ Git is not installed. Please install git first.")
            print("   sudo apt-get install git  # Ubuntu/Debian")
            return False
        print(f"✅ Git found: {stdout}")
        return True
    
    def check_repo_status(self):
        """Check repository status and identify changes"""
        print("\n📊 Checking repository status...")
        
        # Check if it's a git repo
        stdout, stderr, code = self.run_command("git rev-parse --is-inside-work-tree")
        if code != 0:
            print("❌ Not a git repository!")
            return False
        
        # Get current branch
        stdout, _, _ = self.run_command("git branch --show-current")
        self.current_branch = stdout
        print(f"📍 Current branch: {self.current_branch}")
        
        # Get changed files
        stdout, _, _ = self.run_command("git diff --name-only")
        self.changed_files = [f for f in stdout.split('\n') if f]
        
        # Get untracked files
        stdout, _, _ = self.run_command("git ls-files --others --exclude-standard")
        self.untracked_files = [f for f in stdout.split('\n') if f]
        
        # Get status summary
        stdout, _, _ = self.run_command("git status -s")
        
        if not self.changed_files and not self.untracked_files:
            print("ℹ️ No changes detected. Working tree is clean.")
            return "clean"
        else:
            print(f"📝 Changed files: {len(self.changed_files)}")
            print(f"📄 Untracked files: {len(self.untracked_files)}")
            return "dirty"
    
    def show_changes(self):
        """Display detailed changes"""
        print("\n" + "="*60)
        print("📋 DETAILED CHANGES")
        print("="*60)
        
        if self.changed_files:
            print("\n📝 Modified files:")
            for f in self.changed_files[:20]:  # Show first 20
                print(f"   • {f}")
            if len(self.changed_files) > 20:
                print(f"   ... and {len(self.changed_files) - 20} more")
        
        if self.untracked_files:
            print("\n📄 New/Untracked files:")
            for f in self.untracked_files[:20]:
                print(f"   • {f}")
            if len(self.untracked_files) > 20:
                print(f"   ... and {len(self.untracked_files) - 20} more")
        
        # Show diff summary for a few files
        if self.changed_files:
            print("\n🔍 Change summary (first 3 files):")
            for f in self.changed_files[:3]:
                stdout, _, _ = self.run_command(f"git diff --stat {f}")
                if stdout:
                    print(f"   {stdout}")
    
    def add_files(self, files=None):
        """Add files to staging area"""
        print("\n📦 Adding files to staging...")
        
        if files is None or files == "all":
            # Add all changes
            _, stderr, code = self.run_command("git add -A", capture_output=False)
            if code == 0:
                print("✅ Added all changes")
                return True
            else:
                print(f"❌ Failed to add files: {stderr}")
                return False
        else:
            # Add specific files
            for f in files:
                if os.path.exists(os.path.join(self.repo_path, f)):
                    _, stderr, code = self.run_command(f"git add '{f}'", capture_output=False)
                    if code == 0:
                        print(f"✅ Added: {f}")
                    else:
                        print(f"❌ Failed to add: {f}")
                else:
                    print(f"⚠️ File not found: {f}")
            return True
    
    def create_commit_message(self, custom_message=None):
        """Create or get commit message"""
        if custom_message:
            return custom_message
        
        # Generate automatic message based on changes
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        parts = []
        if self.changed_files:
            parts.append(f"Updated {len(self.changed_files)} file(s)")
        if self.untracked_files:
            parts.append(f"Added {len(self.untracked_files)} new file(s)")
        
        if parts:
            message = f"Auto-update: {', '.join(parts)} ({timestamp})"
        else:
            message = f"Auto-update: No significant changes ({timestamp})"
        
        return message
    
    def commit_changes(self, message=None):
        """Commit staged changes"""
        print("\n💾 Committing changes...")
        
        commit_message = self.create_commit_message(message)
        print(f"📝 Commit message: {commit_message}")
        
        # Ask for confirmation
        response = input("\nProceed with commit? (y/n): ").lower()
        if response != 'y':
            print("❌ Commit cancelled")
            return False
        
        # Perform commit
        _, stderr, code = self.run_command(f'git commit -m "{commit_message}"', capture_output=False)
        
        if code == 0:
            print("✅ Commit successful!")
            return True
        else:
            print(f"❌ Commit failed: {stderr}")
            return False
    
    def push_to_github(self, branch=None):
        """Push changes to GitHub"""
        print("\n📤 Pushing to GitHub...")
        
        if branch is None:
            branch = self.current_branch
        
        # Check if remote exists
        stdout, _, _ = self.run_command("git remote -v")
        if not stdout:
            print("❌ No remote repository configured!")
            print("   Run: git remote add origin https://github.com/CHAWAS/nyenje_github.git")
            return False
        
        # Try to push
        _, stderr, code = self.run_command(f"git push origin {branch}", capture_output=False)
        
        if code == 0:
            print("✅ Push successful!")
            return True
        else:
            print(f"❌ Push failed: {stderr}")
            
            # Suggest solutions
            print("\n💡 Possible solutions:")
            print("   1. Check your internet connection")
            print("   2. Run: git pull origin main --rebase")
            print("   3. Check if you have write permission")
            return False
    
    def pull_latest(self):
        """Pull latest changes from GitHub"""
        print("\n📥 Pulling latest changes from GitHub...")
        
        _, stderr, code = self.run_command("git pull origin main", capture_output=False)
        
        if code == 0:
            print("✅ Pull successful!")
            return True
        else:
            print(f"❌ Pull failed: {stderr}")
            return False
    
    def show_log(self, lines=5):
        """Show recent commit log"""
        print(f"\n📜 Last {lines} commits:")
        stdout, _, _ = self.run_command(f"git log --oneline -{lines}")
        print(stdout)
    
    def run_interactive(self):
        """Run interactive update session"""
        print("\n" + "="*60)
        print("🚀 GITHUB UPDATER - Nyenje Bay Tool")
        print("="*60)
        
        # Step 1: Check git
        if not self.check_git_installed():
            return
        
        # Step 2: Check repo status
        status = self.check_repo_status()
        if status == "clean":
            print("\n✅ No changes to commit. Everything is up to date!")
            self.show_log()
            return
        
        # Step 3: Show changes
        self.show_changes()
        
        # Step 4: Ask what to do
        print("\n" + "="*60)
        print("📋 WHAT WOULD YOU LIKE TO DO?")
        print("="*60)
        print("1. Add and commit all changes (recommended)")
        print("2. Add specific files only")
        print("3. View changes in detail")
        print("4. Pull latest changes from GitHub")
        print("5. Cancel")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == "1":
            self.add_files("all")
            if self.commit_changes():
                self.push_to_github()
                self.show_log()
        elif choice == "2":
            print("\nEnter file paths (space-separated):")
            files = input("> ").strip().split()
            if self.add_files(files):
                if self.commit_changes():
                    self.push_to_github()
        elif choice == "3":
            self.run_command("git diff", capture_output=False)
            self.run_interactive()  # Return to menu
        elif choice == "4":
            self.pull_latest()
        else:
            print("❌ Cancelled")
    
    def run_auto(self, message=None):
        """Run automatic update without prompts"""
        print("\n🤖 Running automatic update...")
        
        if not self.check_git_installed():
            return False
        
        status = self.check_repo_status()
        if status == "clean":
            print("✅ No changes to commit")
            return True
        
        # Auto-add all changes
        self.add_files("all")
        
        # Auto-commit
        if self.commit_changes(message):
            # Auto-push
            return self.push_to_github()
        
        return False

def main():
    parser = argparse.ArgumentParser(description='GitHub Auto-Updater for Nyenje Bay Tool')
    parser.add_argument('-a', '--auto', action='store_true', help='Run automatically without prompts')
    parser.add_argument('-m', '--message', type=str, help='Custom commit message')
    parser.add_argument('-p', '--path', type=str, help='Repository path (default: current directory)')
    parser.add_argument('--pull', action='store_true', help='Pull latest changes first')
    
    args = parser.parse_args()
    
    # Get repository path
    if args.path:
        repo_path = args.path
    else:
        repo_path = os.getcwd()
    
    # Create updater
    updater = GitHubUpdater(repo_path)
    
    # Pull if requested
    if args.pull:
        updater.pull_latest()
    
    # Run
    if args.auto:
        success = updater.run_auto(message=args.message)
        sys.exit(0 if success else 1)
    else:
        updater.run_interactive()

if __name__ == "__main__":
    main()