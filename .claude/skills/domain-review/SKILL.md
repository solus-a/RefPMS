---
name: domain-review
description: >-
  RefPMS 코딩 후 도메인 규칙 위반 여부를 검토하고 PASS / WARN / FAIL로 판정합니다.
  domain-reviewer 에이전트에 위임해 별도 컨텍스트에서 실행합니다.
---

# domain-review

코딩 없이 도메인 규칙만 다시 검토하고 싶을 때 수동으로 호출합니다.
검토 규칙은 `.claude/agents/domain-reviewer.md` 한 곳에만 둡니다.

## 실행 방법

`domain-reviewer` 서브에이전트에 아래 작업을 위임합니다.

```
최근 코드 변경사항(미커밋 또는 최근 커밋)을 RefPMS 도메인 규칙으로 검토해
PASS / WARN / FAIL 리포트를 한국어로 작성해줘.
```

Agent 도구를 사용해 `subagent_type: "domain-reviewer"`로 위임하고,
에이전트가 반환한 리포트를 그대로 사용자에게 출력합니다.
