# RefPMS 에이전트 가이드 (AGENTS.md)

이 문서는 `everything-claude-code`의 체계를 기반으로 `RefPMS` 프로젝트에 최적화된 에이전트 운영 지침입니다.

## 핵심 원칙
1. **계획 우선:** 복잡한 변경 전 반드시 `planner` 에이전트와 계획을 수립하십시오.
2. **테스트 주도:** 새 기능이나 버그 수정 시 `tests/harness_runner.py`를 활용한 테스트를 선행하십시오.
3. **모듈 경계 준수:** UI와 비즈니스 로직을 엄격히 분리하고 `refpms-context.mdc`의 규칙을 따르십시오.
4. **보안 및 무결성:** Excel 데이터 처리 시 무결성을 최우선으로 하며 민감한 정보를 노출하지 마십시오.

## 주요 에이전트 역할

| 에이전트 | 역할 | 활용 시점 |
|-------|---------|-------------|
| **planner** | 구현 계획 수립 | 복잡한 기능 추가, 대규모 리팩토링 |
| **architect** | 시스템 설계 및 모듈화 | 아키텍처 결정, 모듈 간 경계 설정 |
| **python-reviewer** | 파이썬 코드 리뷰 | 코드 작성/수정 후 품질 검토 |
| **tdd-guide** | 테스트 주도 개발 가이드 | 새 기능 추가, 버그 수정 시 테스트 작성 |
| **build-error-resolver** | 빌드 및 런타임 에러 해결 | 실행 에러 또는 라이브러리 충돌 시 |
| **doc-updater** | 문서 및 계획 갱신 | `docs/plan.md`, `docs/research.md` 업데이트 |

## 에이전트 협업 워크플로
- **기능 요청 시:** `planner` 호출 → 구현 계획 수립 → `tdd-guide` 호출 → 테스트 작성 → 구현.
- **수정 완료 시:** `python-reviewer` 호출 → 품질 검토 → `doc-updater` 호출 → 문서 갱신.

## 기술 스택 준수 사항
- GUI: **tkinter** (UI 로직 분리 필수)
- Excel: **openpyxl** (데이터 무결성 검증 필수)
- Packaging: **PyInstaller**
- 정적 분석: **ruff**, **black**, **mypy** 권장
