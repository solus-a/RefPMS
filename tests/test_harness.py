from __future__ import annotations

import unittest

from tests.harness_core import discover_cases, run_case


class TestPmsHarness(unittest.TestCase):
    def test_discovered_cases(self) -> None:
        cases = discover_cases()
        if not cases:
            self.skipTest(
                "No harness cases found. Add case files under tests/input and tests/expected."
            )

        for case in cases:
            with self.subTest(case=case.case_name):
                ok, diffs = run_case(case)
                self.assertTrue(ok, msg="\n".join(diffs[:20]))


if __name__ == "__main__":
    unittest.main()

