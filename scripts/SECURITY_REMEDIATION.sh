#!/bin/bash
# CRITICAL SECURITY REMEDIATION SCRIPT
# This script handles the exposed API key situation

echo "=================================================="
echo "SECURITY REMEDIATION FOR EXPOSED API KEY"
echo "=================================================="

cd /workspaces/indegenge_persona

echo ""
echo "Step 1: Checking if .env is tracked by git..."
if git ls-files | grep -q "^\.env$"; then
    echo "⚠️  CRITICAL: .env IS TRACKED BY GIT!"
    echo "Removing .env from git tracking..."
    git rm --cached .env
    echo "✓ Removed .env from git tracking"
else
    echo "✓ Good: .env is NOT tracked by git"
fi

echo ""
echo "Step 2: Checking git history for .env..."
if git log --all --full-history -- .env 2>/dev/null | grep -q "commit"; then
    echo "⚠️  WARNING: .env was committed to git history!"
    echo "The API key has been exposed in git history and must be rotated."
    echo ""
    echo "To remove from history, you need to run:"
    echo "  git filter-branch --force --index-filter \\"
    echo "    'git rm --cached --ignore-unmatch .env' \\"
    echo "    --prune-empty --tag-name-filter cat -- --all"
    echo ""
    echo "OR use BFG Repo-Cleaner (recommended):"
    echo "  https://rtyley.github.io/bfg-repo-cleaner/"
else
    echo "✓ Good: .env was never committed to git history"
fi

echo ""
echo "Step 3: Verifying .gitignore..."
if grep -q "^\.env$" .gitignore; then
    echo "✓ .env is in .gitignore"
else
    echo "⚠️  Adding .env to .gitignore..."
    echo ".env" >> .gitignore
    echo "✓ Added .env to .gitignore"
fi

echo ""
echo "Step 4: Creating .env.example template..."
cat > .env.example <<'EOF'
# PharmaPersonaSim Environment Variables

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# Database Configuration (optional - defaults to SQLite if not set)
DATABASE_URL=sqlite:////workspaces/indegenge_persona/backend/pharma_personas.db

# Backend Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
VITE_API_URL=http://127.0.0.1:8000
EOF
echo "✓ Created .env.example"

echo ""
echo "=================================================="
echo "CRITICAL ACTIONS REQUIRED:"
echo "=================================================="
echo ""
echo "1. ⚠️  IMMEDIATELY REVOKE THE EXPOSED API KEY"
echo "   Go to: https://platform.openai.com/api-keys"
echo "   Find and delete the exposed key immediately!"
echo ""
echo "2. Generate a new OpenAI API key"
echo ""
echo "3. Update your local .env file with the new key"
echo ""
echo "4. NEVER commit .env files to git"
echo ""
echo "5. If .env was in git history, force push after cleaning:"
echo "   git push origin --force --all"
echo "   git push origin --force --tags"
echo ""
echo "=================================================="
