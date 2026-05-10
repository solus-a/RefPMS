---
name: domain-review
description: >-
  RefPMS 코딩 후 도메인 규칙 위반 여부를 빠르게 검토합니다.
  git diff로 변경 내용을 파악하고 PASS / WARN / FAIL로 판정합니다.
---

# domain-review

코딩이 끝난 직후 호출합니다. 최근 변경 사항이 RefPMS 도메인 원칙과 코딩 스타일을 위반하지 않는지 검토하고 한국어로 리포트합니다.

## 검토 절차

### Step 1 — 변경 내용 파악 (병렬 실행)

아래 명령을 동시에 실행합니다.

- `git diff HEAD` — 최근 변경 전체 diff
- `git diff HEAD --name-only` — 변경된 파일 목록
- `git log -3 --oneline` — 최근 커밋 요약

변경된 파일이 중요하거나 diff만으로 판단이 어렵다면 Read로 전체 내용을 확인합니다.

### Step 2 — 규칙 검토

아래 7가지 원칙을 순서대로 적용합니다.

#### [원칙 1] 3계층 계층구조 (CRITICAL)
- `Project → Class → Component` 순서를 엄격히 따를 것.
- 하위 계층이 상위 계층을 직접 참조하거나 수정하면 위반.
- `Material`이라는 용어 사용 금지 — 반드시 `Component`를 사용.

#### [원칙 2] Config Boundary (CRITICAL)
- `config/project/*`, `config/generator/*`, `data/*`는 절대 혼용하지 않을 것.
- Config 접근은 `src/config.py`의 `ProjectConfig` 싱글톤을 통해서만 허용.
- 예: `data/`의 파일을 `config/project/`처럼 취급하면 위반.

#### [원칙 3] 비즈니스 로직 위치
- 도메인 규칙은 엔진 모듈에만 존재: `pms_generator.py`, `class_spec.py`, `thickness_engine.py`, `validator.py`, `project_constraints.py`
- `gui.py`, `main.py`, `controller.py`에 비즈니스 로직이 있으면 위반.

#### [원칙 4] Immutability (CRITICAL)
- 입력 객체를 직접 변경하지 말고 새 객체를 반환할 것.
- 모듈 경계를 넘는 값(settings, config snapshot, class-level bundle 등)은 불변으로 처리.
- `dict.update()`, `list.append()` 등으로 인자를 직접 수정하면 위반.

#### [원칙 5] Constraint > Rule > Default 용어 준수
- `Default`는 덮어쓸 수 있는 값. 필수값처럼 처리하면 위반.
- `Constraint`는 덮어쓸 수 없음. Constraint를 Optional처럼 처리하면 위반.

#### [원칙 6] 코딩 스타일
- Python 기본은 `snake_case`. 기존 rule 헬퍼는 `camelCase` (파일 관례 유지).
- 불리언 변수는 `is_`, `has_`, `should_`, `can_` 접두사.
- 상수는 `UPPER_SNAKE_CASE`, 클래스는 `PascalCase`.
- 파일 길이: 엔진/서비스 모듈은 200~400줄 권장, **800줄 상한**. UI wizard/dialog 파일(`class_template_wizard`, `project_settings_dialog` 등)은 상한 없음 — tkinter 특성상 허용.
- `except: pass` 또는 에러를 무음으로 삼키는 패턴 금지.
- 경계(사용자 입력, 파일, 외부 API)에서만 검증 — 내부 코드는 신뢰.
- YAGNI: feature flag, fallback, shim 등 가상의 미래를 위한 코드 금지.

#### [원칙 7] 연결 누락 확인
- UI를 변경했다면 → 대응 엔진/서비스 로직도 변경되었는지 확인.
- DB 스키마나 JSON 구조를 변경했다면 → 읽기/쓰기 양쪽 모두 업데이트되었는지 확인.
- 새 필드를 추가했다면 → `validator.py`, `pms_generator.py`, template 파일 모두 반영되었는지 확인.
- 새 컴포넌트 그룹이나 타입을 추가했다면 → `component_mapping.json`, `Item_Code_DB.xlsx` 관련 로직도 확인.

### Step 3 — 리포트 작성

아래 형식으로 한국어 리포트를 작성합니다.

```
## 도메인 리뷰 결과

### 변경 요약
- 변경된 파일: (목록)
- 변경 성격: (기능 추가 / 수정 / 삭제)

### 위반 항목
(없으면 "없음")
- [원칙명] 파일명:줄번호 — 설명

### 주의 항목
(위반은 아니지만 확인이 필요한 사항. 없으면 "없음")
- ...

### 종합 판정
PASS / WARN / FAIL — 한 줄 요약
```

**판정 기준:**
- `PASS` — 위반 없음
- `WARN` — 위반은 없으나 주의 항목 존재
- `FAIL` — 명백한 원칙 위반 존재

위반 항목은 반드시 **파일명:줄번호** 형식으로 위치를 명시합니다.
불필요한 설명 없이 간결하게 작성합니다.
