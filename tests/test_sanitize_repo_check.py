from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SanitizeRepoCheckTests(unittest.TestCase):
    def test_sanitize_script_passes_current_tree(self) -> None:
        result = subprocess.run(
            [str(ROOT / "scripts" / "sanitize-repo-check.sh")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
