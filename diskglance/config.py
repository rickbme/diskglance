import json
import os

PATH = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                    "diskglance", "config.json")
DEFAULTS = {"theme": "dark", "notify": True, "show_system": False, "warn": 80, "crit": 90}


def load() -> dict:
    try:
        with open(PATH) as f:
            return {**DEFAULTS, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(cfg: dict):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass
