"""Opt-in navigation composition; the upstream RobotService remains the owner.

No ROS imports, device access, process starts, or torque changes at import time.
An explicitly verified installation profile is required before exposing navigation.
"""

import copy
import json
import math
from pathlib import Path, PurePosixPath
from xlerobot_web_operator.launch_files import launch_file

from xlerobot_web_operator.wheel_only_adapter import (
    BLOCKED,
    WheelOnlyService,
)
from xlerobot_web_operator.wheel_only_adapter import (
    install_command_adapter as install_wheel_adapter,
)


def load_navigation_profile(path):
    data = json.loads(Path(path).resolve(strict=True).read_text(encoding="utf8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported navigation profile")
    for field in (
        "geometry_confirmed",
        "scan_orientation_verified",
        "odometry_verified",
    ):
        if data.get(field) is not True:
            raise ValueError("Navigation commissioning incomplete: " + field)
    radius = data.get("robot_radius")
    if (
        type(radius) not in (int, float)
        or not math.isfinite(radius)
        or not 0.1 <= radius <= 1
    ):
        raise ValueError("Invalid collision envelope")
    transform = data.get("lidar_transform")
    if not isinstance(transform, dict) or set(transform) != {"x", "y", "z", "yaw"}:
        raise ValueError("Explicit lidar transform required")
    if any(
        type(v) not in (int, float) or not math.isfinite(v) for v in transform.values()
    ):
        raise ValueError("Invalid lidar transform")
    if (
        any(abs(transform[k]) > radius for k in ("x", "y"))
        or not 0 <= transform["z"] <= 2
    ):
        raise ValueError("Lidar transform outside installation bounds")
    if abs(transform["yaw"]) > math.pi:
        raise ValueError("Invalid lidar yaw")
    return data


def navigation_parameters(source, profile):
    """Keep upstream safety pipeline and tune only measured collision envelope."""
    result = copy.deepcopy(source)
    for name in ("local_costmap", "global_costmap"):
        params = result[name][name]["ros__parameters"]
        if params.get("footprint"):
            raise ValueError(
                "Review upstream polygon before replacing collision envelope"
            )
        params["robot_radius"] = profile["robot_radius"]
    return result


def install_command_adapter(
    config, wheel_profile, navigation_profile, *, calibration_mode=False
):
    profile = Path(navigation_profile).resolve(strict=True)
    load_navigation_profile(profile)
    install_wheel_adapter(config, wheel_profile, calibration_mode=calibration_mode)
    wheel_command = config.build_process_command
    native_navigation = launch_file("navigation_bringup.launch.py")

    def command(name, options):
        # Recheck commissioning before every process launch, not only server startup.
        load_navigation_profile(profile)
        if name == "bringup":
            args = wheel_command(name, options)
            args[2] = str(native_navigation)
            return [*args, "navigation_profile:=" + str(profile)]
        if name == "mapping":
            return [
                "ros2",
                "launch",
                "lekiwi_cartographer",
                "cartographer.launch.py",
                "configuration_basename:=lekiwi_2d.lua",
            ]
        if name == "navigation":
            # Original RobotService validates selection against its map repository.
            map_path = options.get("map_path")
            if (
                not isinstance(map_path, str)
                or not PurePosixPath(map_path).is_absolute()
            ):
                raise ValueError("Explicit saved map required")
            return [
                "ros2",
                "launch",
                str(launch_file("saved_navigation.launch.py")),
                "map:=" + map_path,
                "navigation_profile:=" + str(profile),
                "operator_nodes:=" + config.OPERATOR_VIEW_NODE_NAME,
            ]
        if name == "save_map":
            return ["ros2", "run", "lekiwi_cartographer", "save_map.sh"]
        raise ValueError("Unsupported navigation process")

    config.build_process_command = command


class NavigationService(WheelOnlyService):
    """Delegate maps/navigation to upstream; keep unrelated arm commands blocked."""

    def get_info(self):
        info = super().get_info()
        info["runtime_profile"] = "navigation"
        # Preserve upstream dependency detection; never claim absent Nav2 is ready.
        info["features"]["has_navigation"] = bool(
            self._service.get_info().get("features", {}).get("has_navigation")
        )
        return info

    def start_process(self, client_id, name, options):
        if name not in ("bringup", "mapping", "navigation"):
            return {
                "ok": False,
                "code": "unavailable",
                "message": "지원하지 않는 프로세스입니다.",
            }
        return self._service.start_process(client_id, name, options)

    def __getattr__(self, name):
        if name in BLOCKED - {
            "save_map",
            "start_exploration",
            "set_initial_pose",
            "send_nav_goal",
        }:
            return super().__getattr__(name)
        return getattr(self._service, name)
