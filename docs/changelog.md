# Changelog

짧은 기록만 둡니다. 상세 이력은 Git 커밋 로그를 사용합니다.

## 2026-04-08

- 볼트: `Bolt_Group` 시트/헤더 및 생성 로직 반영 (`Bolt_Length_Table`은 현재 비활성, 출력 로직 미연동)
- 정렬: `Item_Code` 우선순위의 `G`, `B`를 `project_config.json`의 `output_settings.item_order`로 승격하고, `pms_generator`의 코드 특례 하드코딩 제거
- 문서: `progress.md` 폐지 → `changelog.md` + Cursor 규칙 `refpms-context.mdc`로 일원화
- 템플릿: Branch/Reducing Size 조합 선입력, NPS 제외 규칙(24 초과·0.375/1.25/2.5/3.5)
- 템플릿: PMS 파이프라인이 읽는 열 헤더만 노란색 하이라이트

## 2026-04-07

- `Gasket_Group` 생성·검증·`component_mapping` 조건부 규칙
- `tests/` Golden 하네스 (`harness_core` / `harness_runner`)

## 2026-04-06

- `Flange_Group` 시트·헤더 정리, SW/WN만 SCH 표기, Branch `TH` 전개 보강

## 2026-04-05

- Item_Code DB 스키마, 니플/엘보 규칙, Reducing/Swage 설명·`Dim_Standard` 정규화

## 2026-04-04

- Phase 1~2 모듈(`config`, `class_spec`, `thickness_engine`, `pms_generator`), 템플릿/output 경로 규칙
