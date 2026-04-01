from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to sys.path so we can import modules directly
src_path = str(Path(__file__).resolve().parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from main import main

if __name__ == "__main__":
    main()
