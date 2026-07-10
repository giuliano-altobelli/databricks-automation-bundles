---
name: commit
description: >
    Stage and commit changes using the conventional commit format.
    Invoke when the user asks to commit or after completing a task that should be committed.
version: "1.0.0"
user-invocable: true
context: inline
allowed-tools: Bash
---

# Commit

Conventional commits: `type: description`

**Types:** feat, fix, refactor, docs, tests, chore

**Rules:**
- No co-author attribution or AI-generation notices
- Single-line for simple changes
- Multi-line only when multiple distinct changes need context

**Workflow:**
1. `git status` and `git diff` to understand the changes
2. Stage relevant files
3. Commit using the conventional format

```bash
# Simple
git commit -m "fix: resolve delta table column type"

# Multi-line
git commit -m "$(cat <<'EOF'
fix: resolve delta table column type

- Update column type to INT
- Update column comment
- Handle edge cases when the column is read as a string
EOF
)"
```
