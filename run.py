from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to sys.path so we can import modules directly
src_path = str(Path(__file__).resolve().parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from main import main

if __name__ == "__main__":
    # Command mode:
    # - `python run.py harness ...` -> run automated result-validation harness
    # - no args -> launch GUI
    if len(sys.argv) >= 2 and sys.argv[1].lower() == "harness":
        from tests.harness_runner import main as harness_main

        sys.argv = [sys.argv[0], *sys.argv[2:]]
        raise SystemExit(harness_main())
    main()
