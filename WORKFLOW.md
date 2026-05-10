# WORKFLOW.md — Coding Request Flow

This file defines how Claude should handle user coding requests in RefPMS.
It is referenced from CLAUDE.md but lives separately so it can evolve without touching the project constitution.

## When this flow applies

Apply this flow when the user requests **a change to code or behavior**:
- Adding a feature
- Modifying existing behavior
- Fixing a bug
- Removing a feature

It does NOT apply to:
- Pure questions ("이 함수가 어떻게 동작해?")
- Documentation requests
- Discussions about design / planning without immediate implementation
- Trivial one-line changes (typo fixes, comment edits) — go straight to implementation

## The 6-step flow

```
1. WHY    — intent-clarifier         의도 확정
2. WHAT   — impact-tracer            영향 범위 파악
3. HOW    — implementation-planner   구현 계획 수립
4. DO     — main Claude              구현
5. CHECK  — domain-reviewer          도메인 규칙 검토
6. VERIFY — ui-checklist             수동 테스트 체크리스트
```

Steps 1–3 each invoke a subagent in `.claude/agents/`. Their output is shown to the user.
Step 4 is done by main Claude (the one talking to the user) — implementation requires conversational context, so it is NOT delegated.
Steps 5 and 6 each invoke a subagent. They are independent and **can run in parallel**.

## Routing rules for main Claude

When a coding request comes in:

1. **Invoke `intent-clarifier`** with the user's request. Show its output to the user.
   - If the agent asked questions, wait for the user's answers, then re-invoke with the merged context until the requirements are confirmed.
   - If the requirements are confirmed without questions, proceed.

2. **Invoke `impact-tracer`** with the confirmed requirements. Show its output.

3. **Invoke `implementation-planner`** with both the requirements and the impact analysis. Show the plan to the user.
   - Wait for user confirmation. If they want changes, refine and re-show.

4. **Implement the plan** yourself (main Claude). Use Edit/Write/etc.

5. **After implementation, invoke `domain-reviewer` and `ui-checklist` in parallel** (single message with two Agent tool calls). Show both results.

6. Summarize: implementation done, review result, checklist for the user to follow.

## When to skip steps

- **Trivial change**: typo fix, comment edit, single-line obvious change → skip 1-3, just implement.
- **No UI impact**: backend-only change → skip 6 (ui-checklist).
- **No runtime risk**: pure refactor with no behavior change → step 5 is light, step 6 may be skipped.
- **User explicitly skips**: if user says "그냥 바로 고쳐줘", skip 1-3.

The flow is a default, not a mandate. Use judgment.

## Off-flow tools

These are user-invoked only, not part of the auto flow:

- `/simplify` — built-in skill. Cleans up redundant or messy code. Invoke when the user explicitly asks.
- `/domain-review` — manual trigger for domain-reviewer (when the user wants to re-check without coding).
- `/ui-checklist` — manual trigger for ui-checklist.
- `/pre-code` — manual trigger for intent-clarifier (kept for explicit "let's plan first" use).

## Why this structure

- **Specialized agents**: each one has a narrow responsibility. Easier to maintain and improve in isolation.
- **Auto-routing via descriptions**: Claude reads each agent's `description` field and decides when to invoke. The user just talks naturally.
- **Sequential by necessity**: most steps depend on the previous step's output, so parallelism only applies to 5+6.
- **Implementation stays with main Claude**: coding needs full conversational context, error recovery, and user feedback — not a fit for one-shot subagent delegation.
- **Reversible**: every change goes through git. If the flow misfires, revert and adjust the agent's description.
