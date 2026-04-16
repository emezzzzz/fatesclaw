from __future__ import annotations

import os
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ScriptStaticTests(unittest.TestCase):
    def test_shell_scripts_use_strict_mode(self) -> None:
        for path in (ROOT / "scripts").glob("*.sh"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("set -euo pipefail", text, path)
            self.assertTrue(os.access(path, os.X_OK), path)

    def test_systemd_examples_use_placeholders(self) -> None:
        for path in (ROOT / "config" / "systemd").glob("*.service.example"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("<", text, path)
            self.assertNotRegex(text, r"/home/[A-Za-z0-9._-]+/")
            self.assertNotIn("User=pi", text)

    def test_no_generated_dashboard_artifacts(self) -> None:
        forbidden = {".venv", "agent_panel.egg-info"}
        for path in ROOT.rglob("*"):
            if ".git" in path.parts:
                continue
            self.assertFalse(forbidden & set(path.parts), path)

    def test_no_private_lan_ips_in_text_files(self) -> None:
        private_ip = re.compile(
            r"(^|[^0-9])((10\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])|192\.168)\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)"
        )
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.suffix in {".pyc", ".png", ".dtbo"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertIsNone(private_ip.search(text), path)


if __name__ == "__main__":
    unittest.main()
