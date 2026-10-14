r"""Settings stored in %APPDATA%\Snapclick\settings.json."""
import json
import os
from pathlib import Path

SETTINGS_FILE = Path(os.environ["APPDATA"]) / "Snapclick" / "settings.json"


def load():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(settings):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
