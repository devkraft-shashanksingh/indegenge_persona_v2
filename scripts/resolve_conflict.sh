#!/bin/bash
# Script to resolve git merge conflict

cd /workspaces/indegenge_persona

# Keep our version of the database file
git checkout --ours backend/pharma_personas.db

# Stage the resolved file
git add backend/pharma_personas.db

# Check status
git status

echo "Conflict resolved. Ready to commit."
