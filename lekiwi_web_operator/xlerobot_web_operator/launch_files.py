"""Locate added ROS launches without modifying the upstream workspace packages."""

import importlib.util
from pathlib import Path

NAMES = frozenset({"wheel_only.launch.py", "navigation_bringup.launch.py", "saved_navigation.launch.py"})


def launch_file(name):
    if name not in NAMES:
        raise ValueError("Unsupported extension launch")
    source = Path(__file__).resolve().parent / "launch" / name
    return source.resolve(strict=True)


def load_launch(name):
    spec = importlib.util.spec_from_file_location("xlerobot_added_launch", launch_file(name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
