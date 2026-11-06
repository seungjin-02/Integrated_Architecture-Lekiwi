"""Opt-in device adapter; preserves the original engine and its control lease."""

import copy
import hashlib
import json
from pathlib import Path

import yaml

from xlerobot_web_operator.device_profile import validate_candidate
from xlerobot_web_operator.launch_files import launch_file

CONFIG_SHA = "373547bc902b93cd07dfb498316bdf65b1936e7ebd9f09c36b42914c01f18b23"
LIMITS = {
    "max_linear_x": 0.23,
    "max_linear_y": 0.23,
    "max_linear_speed": 0.23,
    "max_angular_z": 1.53,
}
MESSAGE = "현재 기기는 바퀴 전용 준비 모드입니다. 팔·보정·지도·자율주행은 아직 활성화하지 않았습니다."
BLOCKED = frozenset(
    {
        "arm_start",
        "arm_fold",
        "save_map",
        "start_exploration",
        "set_initial_pose",
        "send_nav_goal",
    }
)


def load_candidate(profile):
    profile = Path(profile).resolve(strict=True)
    if profile.name != "robot_profile.yaml":
        raise ValueError("Expected a prepared device candidate")
    manifest = json.loads(profile.with_name("manifest.json").read_text(encoding="utf8"))
    if manifest.get("kind") != "lekiwi_read_only_device_candidate":
        raise ValueError("Unsupported candidate")
    robot_id = manifest.get("robot_id", "")
    if not robot_id or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for c in robot_id
    ):
        raise ValueError("Invalid candidate identity")
    expected = {"robot_profile.yaml", f"calibration/{robot_id}.json"}
    if set(manifest.get("files", {})) != expected:
        raise ValueError("Unexpected candidate files")
    for name, digest in manifest["files"].items():
        target = (profile.parent / name).resolve(strict=True)
        if (
            not target.is_relative_to(profile.parent)
            or hashlib.sha256(target.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Candidate hash mismatch")
    data = yaml.safe_load(profile.read_text(encoding="utf8"))
    calibration = json.loads(
        (profile.parent / f"calibration/{robot_id}.json").read_text(encoding="utf8")
    )
    validate_candidate(data, calibration)
    return data


def wheel_specs(profile, *, calibration_mode=False):
    data = load_candidate(profile)
    driver = copy.deepcopy(data["lekiwi_motor_driver_node"]["ros__parameters"])
    base = copy.deepcopy(data["lekiwi_base_controller_node"]["ros__parameters"])
    driver.update(wheel_write_enabled=True, arm_write_enabled=calibration_mode is True)
    base.update(enable_motor_write=True, torque_enable=False, **LIMITS)
    return driver, base


def install_command_adapter(config, profile, *, calibration_mode=False):
    """Replace only this process's command factory. Never edit upstream files."""
    path = Path(config.__file__)
    if (
        hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        != CONFIG_SHA
    ):
        raise ValueError("Unsupported native config contract")
    load_candidate(profile)
    launch = launch_file("wheel_only.launch.py")
    profile = Path(profile).resolve()

    def command(name, options):
        if name != "bringup":
            raise ValueError(MESSAGE)
        args = ["ros2", "launch", str(launch), "robot_profile:=" + str(profile)]
        if calibration_mode is True:
            args.append("calibration_mode:=true")
        return args

    config.build_process_command = command


class WheelOnlyService:
    """Capability boundary only; original service retains all safety decisions."""

    def __init__(self, service, *, allow_calibration=False):
        self._service = service
        self._allow_calibration = allow_calibration is True

    def get_info(self):
        info = copy.deepcopy(self._service.get_info())
        info["runtime_profile"] = "wheel_only"
        info.setdefault("features", {}).update(
            has_navigation=False,
            has_arm_control=False,
            has_arm_calibration=self._allow_calibration,
        )
        return info

    def start_process(self, client_id, name, options):
        if name != "bringup":
            return {"ok": False, "code": "unavailable", "message": MESSAGE}
        return self._service.start_process(client_id, name, options)

    def calibration_follower(self, client_id, action, body):
        if not self._allow_calibration:
            return {"ok": False, "code": "unavailable", "message": MESSAGE}
        return self._service.calibration_follower(client_id, action, body)

    def relay_leader(self, *args, **kwargs):
        return False

    def __getattr__(self, name):
        if name in BLOCKED:
            return lambda *args, **kwargs: {
                "ok": False,
                "code": "unavailable",
                "message": MESSAGE,
            }
        return getattr(self._service, name)
