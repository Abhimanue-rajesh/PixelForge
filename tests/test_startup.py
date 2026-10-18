import os
import subprocess
import sys
import unittest
from pathlib import Path


class StartupTests(unittest.TestCase):
    def test_real_launcher_starts_and_exits_in_offscreen_smoke_mode(self):
        root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run(
            [sys.executable, str(root / "run.py"), "--smoke-test"],
            cwd=root, env=environment, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
