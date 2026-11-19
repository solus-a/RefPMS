---
name: pre-code
description: >-
  코딩 요청 전 요구사항을 구조화합니다. intent-clarifier 에이전트에 위임해
  빠진 정보를 질문으로 확인하고 구조화된 요구사항으로 정리합니다.
---

# pre-code

"먼저 요구사항부터 정리하자"고 할 때 수동으로 호출합니다.
절차와 도메인 지식은 `.claude/agents/intent-clarifier.md` 한 곳에만 둡니다.

## 실행 방법

1. Agent 도구로 `subagent_type: "intent-clarifier"`에 사용자 요청을 그대로 넘깁니다.
2. 에이전트가 질문을 반환하면 사용자에게 전달하고, 받은 답을 합쳐 에이전트를 다시 호출합니다. 요구사항이 확정될 때까지 반복합니다.
3. 확정된 "요구사항 정리"를 사용자에게 보여주고 확인을 받습니다.
4. 확인되면 구현으로 바로 가지 않고 `WORKFLOW.md`의 2단계(`impact-tracer`)부터 이어갑니다.
