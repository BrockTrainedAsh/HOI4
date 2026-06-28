# init-repo.ps1
# Run ONCE on Windows to initialize the git repository.
#
# Why this isn't already done: the toolkit files were created from a cloud
# sandbox whose bridge to your Documents folder doesn't allow git's file
# locking/rename operations, so it couldn't run `git init` here. Native Windows
# git has no such limit. This script cleans up any half-created repo and
# initializes cleanly.
#
# Usage (PowerShell, from this folder):
#   Right-click -> "Run with PowerShell"   (or)   ./init-repo.ps1
# If blocked by execution policy:
#   powershell -ExecutionPolicy Bypass -File .\init-repo.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (Test-Path ".git") {
    Write-Host "Removing incomplete .git folder ..."
    Remove-Item -Recurse -Force ".git"
}

git init | Out-Null
git branch -M main

# Ensure a commit identity exists (local to this repo) so the commit can't fail
# with "Author identity unknown". Edit these later if you like.
$haveEmail = (git config user.email) 2>$null
if ([string]::IsNullOrWhiteSpace($haveEmail)) {
    git config user.name  "Brock"
    git config user.email "brockdarnold@gmail.com"
    Write-Host "Set a local git identity (Brock / brockdarnold@gmail.com)." -ForegroundColor Yellow
    Write-Host "Change it any time with: git config user.email you@example.com" -ForegroundColor Yellow
}

git add -A
git commit -m "Initial scaffold: HOI4 memory + mod maintenance toolkit (v0.1)" | Out-Null

Write-Host ""
Write-Host "Repository initialized on branch 'main'." -ForegroundColor Green
git --no-pager log --oneline
Write-Host ""
Write-Host "To publish to GitHub (for the community):"
Write-Host "  1) Create an EMPTY repo at https://github.com/new  (name: HOI4-Memory-Toolkit)"
Write-Host "  2) git remote add origin https://github.com/<your-user>/HOI4-Memory-Toolkit.git"
Write-Host "  3) git push -u origin main"
