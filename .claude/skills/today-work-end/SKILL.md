---
name: today-work-end
description: >-
  End-of-day git wrap-up — review changes, guard .gitignore, commit with a
  meaningful message, and push. Invoke when the user says "TodayWorkEnd",
  "커밋하고 푸쉬", or "커밋하고 푸시".
---

# TodayWorkEnd

Automate the end-of-work git wrap-up: inspect changes, guard `.gitignore`, commit, and push — in one shot.

## Workflow

### Step 1 — Gather state (parallel Bash calls)

Issue these as **separate Bash tool calls in the same message** so they run concurrently. Chaining with `;` inside a single shell invocation is sequential and defeats the point.

- `git status --short --branch --untracked-files=all` — branch, upstream, ahead/behind, tracked + untracked in one shot.
- `git diff HEAD` — staged + unstaged diffs against HEAD.
- `git log -6 --oneline` — recent commit message style.
- `git rev-parse --abbrev-ref --symbolic-full-name '@{u}'` — detect whether an upstream is set (non-zero exit = no upstream).

Also **Read `.gitignore`** so you know the existing patterns and style before proposing additions.

Collect: current branch, upstream (if any), ahead/behind counts, tracked changes, untracked files, commit message conventions.

### Step 2 — Evaluate `.gitignore`

For every **untracked** file or directory, classify it:

| Signal | Action |
|--------|--------|
| Fits an existing tracked pattern (e.g. a new sibling of already-tracked files) | **Commit** |
| Generated artifact, cache, local IDE config, secrets, temp file, editor backup | **Ignore** — add a rule to `.gitignore` |
| Uncertain | **Ask the user** before proceeding |

When adding to `.gitignore`:

1. **Follow the existing style** — grouped with a `# ...` comment header, whitelist exceptions via `!` where the repo already does.
2. **Handle already-tracked files**: if a path you now want to ignore is *already tracked*, `.gitignore` alone won't exclude it. Untrack with `git rm --cached -r -- <path>` and include that in the commit. Confirm with the user before removing tracked content.
3. **Re-verify**: after editing `.gitignore`, run `git status --short --untracked-files=all` again and confirm the intended paths are gone (or still listed, for whitelists).
4. Stage `.gitignore` together with the related changes so the commit is self-consistent.

### Step 3 — Decide what this run should do

Branch on the state collected in Step 1:

- **Working tree dirty** (staged or unstaged changes, or to-be-committed untracked files) → proceed to Step 4.
- **Working tree clean but `ahead > 0`** (unpushed commits exist) → skip to Step 5 (push only). Tell the user you're pushing existing commits without creating a new one.
- **Working tree clean and `ahead == 0`** → nothing to do. Report "no changes, nothing to push" and stop. Do not create an empty commit.
- **Upstream is `behind` or `diverged`** → **do not** silently pull/rebase/merge. Surface the situation to the user and ask how to proceed.

### Step 4 — Stage & commit

1. Stage the relevant files with `git add -- <paths>`. Prefer explicit paths over `git add -A` so accidental files don't slip in.
2. **Verify the staging area** — run `git status --short` and `git diff --staged --stat`, then assert ALL of:
   - Every path staged in `git status` was either (a) an untracked file classified "Commit" in Step 2, or (b) a tracked file whose diff appeared in Step 1's `git diff HEAD` output.
   - No path classified "Ignore" or "Ask" in Step 2 is staged.
   - No file that looks like a secret (`.env`, `*credential*`, `*token*`, private key) is staged.
   - `.gitignore` is staged **only if** it was modified in Step 2.

   If any assertion fails, unstage the offending path with `git reset HEAD -- <path>` and explain to the user why it was removed.
3. Draft a commit message:
   - Match the style of recent commits (language, casing, scope prefix).
   - Subject ≤ ~72 chars, imperative mood, focuses on **why**.
   - Optional 1–2 sentence body for rationale or side effects.
4. Commit with a HEREDOC so multi-line formatting is preserved:

   ```bash
   git commit -m "$(cat <<'EOF'
   subject line

   body paragraph if needed
   EOF
   )"
   ```

5. **Pre-commit hook handling**:
   - Hook **rejected** the commit (non-zero exit) → fix the reported issue and create a **new** commit. Do **not** `--amend`.
   - Hook **succeeded but auto-modified files** → `git add` the modified paths; `git commit --amend --no-edit` is acceptable *only* if this commit was created in this session and has not been pushed.

### Step 5 — Push

1. If Step 1 found no upstream, use `git push -u origin HEAD`. Otherwise `git push`.
2. On failure, diagnose before retrying — never force-push or pull/rebase without explicit user approval:
   - **Non-fast-forward / rejected** → stop and ask the user whether to rebase, merge, or force-push.
   - **Auth / network error** → report verbatim and stop.
   - **Pre-push hook failure** → fix the reported issue, then retry.

### Step 6 — Confirm

Run these verifications and report back:

- `git status --short --branch` — working tree should be clean and the branch should not be `ahead` of upstream.
- `git log -1 --oneline` — the new commit hash + subject (if a commit was made).
- `git log "@{u}..HEAD" --oneline` — must be empty, proving everything is pushed.

Include in the final report: commit hash(es) and subject, files included, push result, working-tree status.

## Decision Rules

- **Never** commit files that look like secrets (`.env`, credentials, tokens, private keys). If the user explicitly asks, warn first.
- **Never** force-push, amend a pushed commit, or silently rewrite history — require explicit user consent.
- **Never** run `git pull`, `git rebase`, or `git merge` autonomously to resolve a diverged branch — ask the user.
- If the user's intent is ambiguous (e.g. mixed unrelated changes), ask whether to split into multiple commits before staging.

## Platform Note

The project's daily platform is Windows + PowerShell, but Claude Code's Bash tool runs bash (Git Bash on Windows). Use bash syntax — heredocs (`<<'EOF'`), forward slashes in paths, `/dev/null` — for all commands in this skill.
