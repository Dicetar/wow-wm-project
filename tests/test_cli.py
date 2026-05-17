from __future__ import annotations

import contextlib
import io
import unittest

from wm.cli import CATALOG, main


class WmCliDispatchTests(unittest.TestCase):
    def test_list_prints_catalog(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["--list"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("wm - World Master CLI", out)
        self.assertIn("control.inspect", out)

    def test_no_args_prints_catalog(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([])
        self.assertEqual(rc, 0)
        self.assertIn("Usage:", buf.getvalue())

    def test_unknown_command_returns_2(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = main(["bogus.thing"])
        self.assertEqual(rc, 2)
        self.assertIn("unknown command", buf.getvalue())

    def test_dispatches_to_real_module(self) -> None:
        # `subjects.inspect` requires --entry; argparse exits non-zero, proving
        # the dispatcher actually executed the target module's __main__.
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = main(["subjects.inspect"])
        self.assertNotEqual(rc, 0)
        self.assertIn("usage", buf.getvalue().lower())

    def test_catalog_targets_are_importable(self) -> None:
        import importlib

        for entries in CATALOG.values():
            for name, _desc in entries:
                with self.subTest(name=name):
                    importlib.import_module(f"wm.{name}")


if __name__ == "__main__":
    unittest.main()
