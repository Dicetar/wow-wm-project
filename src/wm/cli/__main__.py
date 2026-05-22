"""`python -m wm.cli` runs the unified WM CLI dispatcher.

(The slice demo is still reachable directly via `python -m wm.cli.slice_demo`.)
"""
from wm.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
