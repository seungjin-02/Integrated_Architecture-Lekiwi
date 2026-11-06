"""Wheel-only composition of upstream nodes. No arm/sensor or torque-on launch."""

import stat
import subprocess
import sys
from pathlib import Path


def _extension_root():
    import os
    from pathlib import Path
    explicit = os.environ.get("XLEROBOT_SOURCE_ROOT")
    candidates = ([Path(explicit)] if explicit else []) + [Path.cwd()]
    candidates += [p / "lekiwi_web_operator" for p in Path(__file__).resolve().parents]
    for candidate in candidates:
        if (candidate / "xlerobot_web_operator/__init__.py").is_file():
            return candidate.resolve()
    raise RuntimeError("Set XLEROBOT_SOURCE_ROOT to the extension backend directory")


def generate_launch_description():
    from launch import LaunchDescription
    from launch.actions import (
        DeclareLaunchArgument,
        EmitEvent,
        OpaqueFunction,
        RegisterEventHandler,
    )
    from launch.event_handlers import OnProcessExit
    from launch.events import Shutdown
    from launch.substitutions import LaunchConfiguration
    from launch_ros.actions import Node

    root = str(_extension_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from xlerobot_web_operator.wheel_only_adapter import wheel_specs

    def setup(context):
        driver_params, base_params = wheel_specs(
            LaunchConfiguration("robot_profile").perform(context),
            calibration_mode=LaunchConfiguration("calibration_mode")
            .perform(context)
            .lower()
            == "true",
        )
        port = Path(driver_params["port"]).resolve(strict=True)
        if not port.is_relative_to("/dev") or not stat.S_ISCHR(port.stat().st_mode):
            raise RuntimeError("Configured serial device is unavailable")
        if (
            subprocess.run(
                ["fuser", str(port)], capture_output=True, check=False
            ).returncode
            != 1
        ):
            raise RuntimeError("Serial ownership could not be confirmed free")
        driver = Node(
            package="lekiwi_motor_driver",
            executable="lekiwi_motor_driver_node",
            parameters=[driver_params],
            output="screen",
        )
        base = Node(
            package="lekiwi_base_controller",
            executable="lekiwi_base_controller_node",
            parameters=[base_params],
            output="screen",
        )
        # A failed node ends the entire managed launch instead of leaving half a stack.
        guards = [
            RegisterEventHandler(
                OnProcessExit(
                    target_action=node,
                    on_exit=[EmitEvent(event=Shutdown(reason="wheel node exited"))],
                )
            )
            for node in (driver, base)
        ]
        return [*guards, driver, base]

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_profile"),
            DeclareLaunchArgument("calibration_mode", default_value="false"),
            OpaqueFunction(function=setup),
        ]
    )
