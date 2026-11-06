"""Existing wheel launch plus TF and filtering for the separately owned /scan."""


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
    import sys
    from pathlib import Path

    from launch import LaunchDescription
    from launch.actions import (
        DeclareLaunchArgument,
        EmitEvent,
        IncludeLaunchDescription,
        OpaqueFunction,
        RegisterEventHandler,
    )
    from launch.event_handlers import OnProcessExit
    from launch.events import Shutdown
    from launch.launch_description_sources import PythonLaunchDescriptionSource
    from launch.substitutions import LaunchConfiguration
    from launch_ros.actions import Node

    root = _extension_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from xlerobot_web_operator.navigation_adapter import load_navigation_profile

    def setup(context):
        data = load_navigation_profile(
            LaunchConfiguration("navigation_profile").perform(context)
        )
        transform = data["lidar_transform"]
        wheels = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(root / "xlerobot_web_operator/launch/wheel_only.launch.py")),
            launch_arguments={
                "robot_profile": LaunchConfiguration("robot_profile"),
                "calibration_mode": LaunchConfiguration("calibration_mode"),
            }.items(),
        )
        tf = Node(
            package="tf2_ros",
            executable="static_transform_publisher",
            name="xlerobot_lidar_transform",
            arguments=[
                "--x",
                str(transform["x"]),
                "--y",
                str(transform["y"]),
                "--z",
                str(transform["z"]),
                "--yaw",
                str(transform["yaw"]),
                "--frame-id",
                "base_footprint",
                "--child-frame-id",
                "lidar_link",
            ],
        )
        scan = Node(
            package="lekiwi_scan_filter",
            executable="lekiwi_scan_filter_node",
            name="lekiwi_scan_filter_node",
            parameters=[
                {
                    "input_topic": "/scan",
                    "output_topic": "lekiwi/sensor/scan_filtered",
                    "base_frame": "base_footprint",
                    "self_radius": min(0.19, data["robot_radius"]),
                    "min_intensity": 0.0,
                    "mask_wheels": False,
                }
            ],
        )
        guards = [
            RegisterEventHandler(
                OnProcessExit(
                    target_action=node,
                    on_exit=[
                        EmitEvent(
                            event=Shutdown(
                                reason="navigation sensor composition exited"
                            )
                        )
                    ],
                )
            )
            for node in (tf, scan)
        ]
        return [*guards, wheels, tf, scan]

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_profile"),
            DeclareLaunchArgument("navigation_profile"),
            DeclareLaunchArgument("calibration_mode", default_value="false"),
            OpaqueFunction(function=setup),
        ]
    )
