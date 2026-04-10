import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path


class RuntimeDllGuardTests(unittest.TestCase):
    def test_guard_passes_and_fails_on_hash_mismatch(self) -> None:
        root = Path(".tmp/runtime_dll_guard")
        if root.exists():
            shutil.rmtree(root)
        try:
            root.mkdir(parents=True)
            names = ["libmysql.dll", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "legacy.dll"]
            files = []
            for name in names:
                payload = f"{name}:v1".encode("utf-8")
                path = root / name
                path.write_bytes(payload)
                files.append(
                    {
                        "name": name,
                        "length": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
            lock = root / "runtime-dlls.lock.json"
            lock.write_text(json.dumps({"schema_version": "wm.runtime_dlls.v1", "files": files}), encoding="utf-8")

            script = Path("scripts/bootstrap/Test-RuntimeDllGuard.ps1")
            ok = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-BinRoot",
                    str(root),
                    "-LockPath",
                    str(lock),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr or ok.stdout)

            (root / "legacy.dll").write_text("wrong", encoding="utf-8")
            failed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-BinRoot",
                    str(root),
                    "-LockPath",
                    str(lock),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("Runtime DLL mismatch", failed.stderr + failed.stdout)
        finally:
            if root.exists():
                shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
