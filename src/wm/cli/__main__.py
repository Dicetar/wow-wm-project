"""Default CLI entrypoint for `python -m wm.cli` — runs the slice demo."""
from wm.cli.slice_demo import main

if __name__ == "__main__":
    raise SystemExit(main())
