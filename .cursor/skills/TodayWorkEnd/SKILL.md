---
name: today-work-end
description: >-
  End-of-day git workflow: review changes, evaluate .gitignore coverage,
  commit with a meaningful message, and push. Use when the user says
  "TodayWorkEnd", "커밋하고 푸쉬", or "커밋하고 푸시".
---

# TodayWorkEnd

Automate the end-of-work git wrap-up: inspect changes, guard .gitignore,
commit, and push — in one shot.

## Workflow

### Step 1 — Gather State (run in parallel)

```bash
git status --short --branch
git status --short --untracked-files=all
git diff --staged
git diff
git log -6 --oneline
```

Collect: branch name, tracked remote, untracked files, staged/unstaged diffs,
recent commit message style.

### Step 2 — Evaluate .gitignore

For every **untracked** file or directory, decide whether it should be
committed or ignored.

| Signal | Action |
|--------|--------|
| File fits an existing tracked pattern (e.g. new `.cursor/rules/*.mdc` when others are tracked) | **Commit** |
| Generated artifact, cache, local IDE config, secrets, temp file | **Ignore** — add a rule to `.gitignore` |
| Uncertain | **Ask the user** before proceeding |

If `.gitignore` is modified, stage and include it in the commit.

### Step 3 — Stage & Commit

1. Stage all relevant files (`git add`).
2. Draft a concise commit message:
   - Follow the style of recent commits in the repo.
   - Focus on **why**, not **what**.
   - 1-2 sentence body when helpful.
3. Commit using a HEREDOC (PowerShell or bash, per user's shell).

### Step 4 — Push

```bash
git push
```

If the branch has no upstream, use `git push -u origin HEAD`.

### Step 5 — Confirm

Run `git status --short --branch` and report:
- Commit hash and message
- Files included
- Push result
- Working tree cleanliness

## Decision Rules

- **Never** commit files that look like secrets (`.env`, credentials, tokens).
  Warn the user if they explicitly request it.
- **Never** force-push or amend unless the user explicitly asks.
- If there are **no changes** at all, inform the user and stop.
- If the commit is rejected by a pre-commit hook, fix and create a **new**
  commit (do not amend).

## Shell Compatibility Note

This project runs on Windows (PowerShell). Use `;` instead of `&&` to chain
commands. For commit messages use PowerShell here-strings (`@'...'@`) or
the `"$(cat <<'EOF' ... EOF)"` form on bash/Git Bash.
