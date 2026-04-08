# RefPMS 프로젝트 헌법 (Project Constitution)

이 문서는 RefPMS 프로젝트를 수행할 때 에이전트가 반드시 준수해야 하는 지침입니다. Cursor 규칙(`.cursor/rules/`)과 충돌하면 저장소의 **alwaysApply 규칙**을 우선합니다.

## 1. 최우선 동작 수칙 (Core Mandates)

- **문서 선 분석:** 코드 수정·실행 전 `docs/plan.md`를 읽고, 필요 시 `docs/research.md` 또는 `docs/changelog.md`를 본다. 불변 운영 규칙은 `.cursor/rules/refpms-context.mdc`에 있다.
- **진행 기록:** `docs/progress.md`는 사용하지 않는다. 의미 있는 변경은 `docs/changelog.md`에 짧게 남기고, 상세는 Git 커밋으로 남긴다. (`docs/chat/` 일일 기록은 필수 아님.)
- **문서 동기화:** 로드맵이 바뀌면 `docs/plan.md`를, 아키텍처가 바뀌면 `docs/research.md`를 갱신한다. `.cursor/rules/docs-workflow.mdc`의 슬림 정책을 따른다.
