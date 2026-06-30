---
name: copilot-pr
description: "Trigger: create PR, open pull request, review PR, revisar PR, crear PR, describe PR. Generate PR title+body from branch diff and review an open PR for correctness and quality."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Activation Contract

Use this skill when:
- User asks to create, open, or prepare a PR
- User asks to review, check, or audit an open PR
- User asks to describe or title a PR

## Hard Rules

1. **Title**: conventional commit prefix + imperative summary, max 70 chars. No period.
2. **Body**: always include Summary, Test plan, and Deferred sections. No filler.
3. **Review**: report only actionable findings — CRITICAL (blocks merge), WARNING (should fix), SUGGESTION (optional). Skip praise.
4. **Never push or merge** without explicit user confirmation.
5. Use `gh` CLI for all GitHub operations — no manual curl.

## Workflow — Create PR

```
1. git diff main...HEAD          → understand scope
2. git log main...HEAD --oneline → understand commits
3. Draft title (conventional commit format)
4. Draft body (see template in assets/pr-body.md)
5. gh pr create --title "..." --body "$(cat <<'EOF' ... EOF)"
6. Return PR URL
```

## Workflow — Review PR

```
1. gh pr diff <number>           → get full diff
2. gh pr view <number>           → get title, body, labels
3. Read changed files for context (up to 5 key files)
4. Report findings grouped by severity:
   - CRITICAL: correctness bugs, security issues, broken contracts
   - WARNING:  missing error handling, test gaps, perf issues
   - SUGGESTION: style, simplification, naming
5. If --fix flag: apply CRITICAL fixes, re-run typecheck/tests
6. If --comment flag: post findings as inline PR comments via gh api
```

## Decision Gates

| Situation | Action |
|-----------|--------|
| No open PR, user says "create" | Run Create workflow |
| PR number given, user says "review" | Run Review workflow |
| Both requested | Create first, then review |
| Diff > 400 lines | Warn user, suggest /chained-pr |
| Tests failing | Block PR creation, report failures |

## Output Contract

**Create:** return PR URL + one-line summary of what was opened.
**Review:** return grouped findings table. If nothing blocking: "No blockers found."
