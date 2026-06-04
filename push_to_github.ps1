param(
    [string]$RepoName = "邮箱注册"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "========================================"
Write-Host " Push to GitHub Private Repo"
Write-Host "========================================"

# 1. Check git
Write-Host ""
Write-Host "[1/5] Checking git..."
try {
    $v = git --version 2>&1
    Write-Host "  git: $v"
} catch {
    Write-Host "  ERROR: git not found. Install from https://git-scm.com/download/win"
    exit 1
}

# 2. Check gh CLI
Write-Host ""
Write-Host "[2/5] Checking GitHub CLI..."
$hasGh = $false
try {
    $ghv = gh --version 2>&1 | Select-Object -First 1
    Write-Host "  gh: $ghv"
    $hasGh = $true
} catch {
    Write-Host "  WARNING: gh CLI not found, will use manual method"
    Write-Host "  Install: winget install GitHub.cli"
}

# 3. Init git
Write-Host ""
Write-Host "[3/5] Initializing git repo..."
if (-not (Test-Path ".git")) {
    git init
    git branch -M main
    Write-Host "  Initialized git repo"
} else {
    Write-Host "  Git repo already exists"
}

$userName = git config user.name 2>&1
$userEmail = git config user.email 2>&1
if (-not $userName) {
    $name = Read-Host "  Enter git username"
    git config user.name $name
}
if (-not $userEmail) {
    $email = Read-Host "  Enter git email"
    git config user.email $email
}

# 4. Add and commit
Write-Host ""
Write-Host "[4/5] Adding files..."
git add -A
$status = git status --short
if ($status) {
    Write-Host "  Staged files:"
    $status | ForEach-Object { Write-Host "    $_" }
} else {
    Write-Host "  No new files to commit"
}

$commitMsg = Read-Host "  Commit message (Enter for default)"
if (-not $commitMsg) { $commitMsg = "feat: multi-provider CDP auto registration framework" }

git commit -m $commitMsg 2>&1
Write-Host "  Committed"

# 5. Push to GitHub
Write-Host ""
Write-Host "[5/5] Pushing to GitHub..."

if ($hasGh) {
    $inputName = Read-Host "  Repo name (Enter for $RepoName)"
    if ($inputName) { $RepoName = $inputName }

    Write-Host "  Creating private repo: $RepoName..."
    gh repo create $RepoName --private --source=. --push
    Write-Host ""
    Write-Host "  Push complete!"
    $login = gh api user --jq '.login'
    Write-Host "  Repo: https://github.com/$login/$RepoName"
} else {
    Write-Host "  Create a private repo on GitHub, then run:"
    Write-Host "    git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git"
    Write-Host "    git push -u origin main"
}

Write-Host ""
Write-Host "========================================"
Write-Host " Done!"
Write-Host "========================================"

