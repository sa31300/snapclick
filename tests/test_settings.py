"""SNAPCLICK_SETTINGS: test runs use their own settings file and never touch the startup list."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Runs in a fresh Python, so the module reads the environment variable at import.
CHECK = """
import winreg
def blocked(*args, **kwargs):
    raise AssertionError("the Run key was opened")
winreg.OpenKey = blocked
from snapclick import settings
settings.save(dict(settings.load(), start_with_windows=True))
assert settings.set_start_with_windows(True)
assert settings.set_start_with_windows(False)
print(settings.SETTINGS_FILE)
"""


class TestSettingsFile(unittest.TestCase):
    def test_test_settings_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            env = dict(os.environ, SNAPCLICK_SETTINGS=str(path))
            out = subprocess.run([sys.executable, "-c", CHECK], cwd=ROOT, env=env,
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout.strip(), str(path))
            self.assertIn('"start_with_windows": true', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
