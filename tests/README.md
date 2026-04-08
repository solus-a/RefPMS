# Test Harness

이 폴더는 결과값 기반 자동 검증(하네스) 전용입니다.

## 목적

- **출력 동작이 바뀌는 변경**은 `docs/` 장문 기록보다 **여기에 케이스 추가·expected 갱신**을 우선합니다.
- 사람이 엑셀 결과를 눈으로 비교하는 수동 테스트를 줄입니다.
- `input -> generator -> actual output` 과 `expected output` 을 자동 비교합니다.
- 비교 결과를 Pass/Fail로 즉시 판단합니다.

## 폴더 규칙

- 입력: `tests/input/<case_name>/Class_Define_Template.xlsx`
- 기대결과: `tests/expected/<case_name>/Piping_Material_Class_Data.xlsx`

`<case_name>`은 동일해야 하며, 폴더가 미러 구조여야 합니다.

## 실행

- 전체 케이스: `python -m tests.harness_runner --all`
- 단일 케이스: `python -m tests.harness_runner --case gasket-group-basic`
- 사용자 지정 파일:  
  `python -m tests.harness_runner --input template/20260405_142914/Class_Define_Template.xlsx --expected output/20260406_233338/Piping_Material_Class_Data.xlsx`

## 자동 테스트(유닛테스트 러너)

- `python -m unittest tests.test_harness -v`

