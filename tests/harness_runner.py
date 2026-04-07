from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tests.harness_core import HarnessCase, discover_cases, run_case


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Result-validation harness for PMS generator."
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Case folder name under tests/input and tests/expected. Repeatable.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Custom input template .xlsx path (used with --expected).",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        help="Custom expected output .xlsx path (used with --input).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all discovered mirrored cases in tests/input and tests/expected.",
    )
    return parser.parse_args()


def _build_cases(args: argparse.Namespace) -> list[HarnessCase]:
    cases: list[HarnessCase] = []
    if args.input or args.expected:
        if not args.input or not args.expected:
            raise ValueError("--input and --expected must be provided together.")
        cases.append(
            HarnessCase(
                case_name="custom",
                input_path=args.input.resolve(),
                expected_path=args.expected.resolve(),
            )
        )

    if args.all:
        discovered = discover_cases()
        if not discovered:
            print(
                "No discovered cases under tests/input and tests/expected. "
                "Add mirrored case folders first."
            )
        cases.extend(discovered)

    if args.case:
        for case_name in args.case:
            input_path = Path("tests") / "input" / case_name / "Class_Define_Template.xlsx"
            expected_path = (
                Path("tests")
                / "expected"
                / case_name
                / "Piping_Material_Class_Data.xlsx"
            )
            cases.append(
                HarnessCase(
                    case_name=case_name,
                    input_path=input_path.resolve(),
                    expected_path=expected_path.resolve(),
                )
            )
    return cases


def main() -> int:
    args = _parse_args()
    try:
        cases = _build_cases(args)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    if not cases:
        print("No cases selected. Use --all, --case <name>, or --input/--expected.")
        return 2

    failures = 0
    for case in cases:
        ok, diffs = run_case(case)
        if ok:
            print(f"PASS: {case.case_name}")
            continue
        failures += 1
        print(f"FAIL: {case.case_name}")
        for line in diffs[:20]:
            print(f"  {line}")
        if len(diffs) > 20:
            print(f"  ... and {len(diffs) - 20} more differences")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

