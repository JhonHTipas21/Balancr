---
name: git-commit-policy
description: Guidelines for committing code, structuring messages, using correct author credentials, and avoiding emojis.
---

# Git Commit Policy

Always adhere to these guidelines when making commits or managing Git history in the Balancr repository.

## Credentials
Every local commit must be made using the following verified credentials:
- **Name**: `JhonHTipas21`
- **Email**: `168132558+JhonHTipas21@users.noreply.github.com`

Verify local configuration before committing:
```bash
git config user.name
git config user.email
```

## Commit Message Formatting
1. Use the Conventional Commits specification:
   - `feat: ...` for new features
   - `fix: ...` for bug fixes
   - `chore: ...` for maintenance or workflow changes
   - `docs: ...` for documentation updates
   - `test: ...` for adding/fixing tests
2. **Never use emojis** in commit messages, Pull Request titles, or README descriptions. Maintain a highly professional, concrete, and corporate tone.
3. Write commit messages, code comments, docstrings, and context in **English**.
