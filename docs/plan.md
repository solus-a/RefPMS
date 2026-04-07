# RefPMS 실행 계획 (Plan)

RefPMS를 5단계 계층 스키마 기반 데이터 엔진으로 완성하기 위한 로드맵입니다.
이 문서는 "무엇을 언제 끝낼지"에 집중하며, 상세 이력은 `docs/progress.md`를 기준으로 관리합니다.

---

## Phase 1. Project Context Externalization (완료)
**목표:** 하드코딩 상수를 프로젝트 설정으로 분리

- [x] `project_config.json` 도입 (`unit_system`, `nps_master`, `output_settings`, `coding_rules`)
- [x] `src/config.py` 설정 로더/접근 경로 정비
- [x] `src/pms_generator.py`의 상수 참조를 설정 기반으로 전환

## Phase 2. Class/Spec Technical Envelope (완료)
**목표:** 클래스 제약/두께 룩업/기본 검증 정형화

- [x] `src/class_spec.py` (`ClassSpec`, 클래스 제약 경고 로직)
- [x] `src/thickness_engine.py` (Schedule 룩업 + 범위 폴백)
- [x] B16.5/B16.11 등급 비교 분리 및 재질 allowlist 연동
- [x] Reducing/Branch 테이블 기반 전개 정합

## Phase 3. Group Logic Generalization (완료)
**목표:** 부품군 검증/전개/설명 규칙의 운영 가능 상태 확보

- [x] `data/component_mapping.json` + `src/validator.py` 연동
- [x] `Gasket_Group` 시트/설명/검증 규칙 반영
- [x] `Flange_Group` 네이밍/컬럼 정리 및 설명 규칙 반영
- [x] `tests/` 하네스 도입(입력/기대 결과 자동 비교)

## Phase 4. Attribute Atomization (진행 예정)
**목표:** 설명 문자열 중심 로직을 원자 속성 중심 구조로 전환

- [ ] 공통 원자 속성 스키마 정의 (`Item_Code`, `Group`, `Size`, `Base_Mat`, `Desc`, `Remarks`)
- [ ] 부품군별 상세 원자 속성 정리 (Valve Trim 이중 관리 포함)
- [ ] `formatter` 계층(규칙 기반 설명 조합기) 설계/구현

## Phase 5. Atomic Generation & Export (미착수)
**목표:** 원자 속성 기반 최종 산출/리포트 체계 완성

- [ ] Flat Data 통합 출력
- [ ] 부품군별 분리 출력 병행 지원
- [ ] GUI 검증 리포트/진행률 표시

---

## 현재 상태

- **Current Phase:** Phase 3 완료
- **In Progress:** 테스트 케이스 확충 + Phase 4 설계 착수 준비
- **Blockers:** 없음

## 다음 액션 (우선순위)

1. `tests/input` / `tests/expected` 실케이스 추가
2. 하네스 기준으로 핵심 케이스 PASS 기준선 확정
3. Phase 4 데이터 모델 초안 작성 (`research.md`와 동기화)

## 성공 기준

- [x] 프로젝트 설정 기반 동작 (단위/사이즈/정렬 규칙)
- [x] 운영 규칙 기반 부품군 생성/검증
- [x] 하네스 기반 결과값 자동 검증 경로 확보
- [ ] 원자 속성 기반 설명 자동 생성
- [ ] 분리/통합 출력 동시 지원
