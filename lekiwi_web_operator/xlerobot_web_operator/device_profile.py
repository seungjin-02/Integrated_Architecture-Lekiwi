#!/usr/bin/env python3
"""Prepare a NEW read-only device candidate from a saved guarded READ inventory.

Purely offline: no serial/ROS/SSH imports, device access, calibration writes or
runtime configuration changes. Calibration JSON is an EEPROM snapshot, not a
claim that physical limits, arm rest pose or driving directions were verified.
"""

import argparse
import copy
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml

ARM_NAMES = (
    "arm_shoulder_pan",
    "arm_shoulder_lift",
    "arm_elbow_flex",
    "arm_wrist_flex",
    "arm_wrist_roll",
    "arm_gripper",
)
WHEEL_NAMES = ("base_left_wheel", "base_back_wheel", "base_right_wheel")
REGISTERS = {"3": 2, "9": 4, "31": 2, "33": 1, "40": 1, "56": 15}
SDK_READ_SHA256 = "44920a0b2c707491b65efffba847d10298d1faf9bf10d91eddeb37f7236153c6"
UPSTREAM_COMMIT = "7ea3da19dee975c34907677f40e823c256fbefdb"
SOURCE_HASHES = {
    "src/lekiwi_motor/lekiwi_base_controller/config/lekiwi_base_controller.yaml": "7a737ffd19732f1ebe7a44a050a8f54727ac175f65e9dcf4b243afd7b7654710",
    "src/lekiwi_description/config/base_frame.yaml": "8448389410752830df4685cb5eba7fd49ffc889f553353255d59282fbbf838c3",
    "src/lekiwi_bringup/config/robot_profile.yaml": "1aae0e823bd481c0e33660f1ea51c691cf6866042254439053a1afc924d015f0",
    "src/lekiwi_motor/lekiwi_motor_driver/config/lekiwi_motor_driver.yaml": "fa894fee4abf9bdb848eedbfa1ec8455095558aa354dab275fc6c4865cfe8909",
    "src/lekiwi_lerobot/config/follower_arm.yaml": "6a01feca83056bc0466897584bca2d58fc5d80acfe97b3b4961f5c0a228a5837",
}
WHEEL_CONTRACT = {
    "wheel_ids": [8, 9, 7],
    "wheel_directions": [1.0, 1.0, 1.0],
    "wheel_radius": 0.05,
    "base_radius": 0.13647,
    "kinematics_frame_x": 0.007587843843,
    "kinematics_frame_y": -0.010776931094,
    "kinematics_frame_yaw": 2.094379865161,
    "encoder_odom_scale": 1.0,
}


class ProfileError(ValueError):
    """Fixed error codes never echo arbitrary inventory content."""


def _require(condition, code):
    if not condition:
        raise ProfileError(code)


def _integer(value, minimum=0, maximum=4095):
    return type(value) is int and minimum <= value <= maximum


def _timestamp(value):
    _require(isinstance(value, str) and len(value) <= 64, "invalid_observed_at")
    try:
        parsed = datetime.fromisoformat(value)
        _require(
            parsed.tzinfo is not None and parsed.utcoffset() is not None,
            "invalid_observed_at",
        )
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        raise ProfileError("invalid_observed_at") from None


def _word(data):
    return data[0] | data[1] << 8


def validate_inventory(data):
    """Decode raw register bytes, then require summary fields to agree exactly."""
    _require(isinstance(data, dict), "invalid_inventory")
    fields = {
        "observed_at",
        "port",
        "resolved_port",
        "baud",
        "sdk_read_source_sha256",
        "write_instructions_allowed",
        "motors",
        "read_packets_sent",
    }
    _require(set(data) == fields, "invalid_inventory_schema")
    observed_at = _timestamp(data["observed_at"])
    _require(data["write_instructions_allowed"] is False, "unsafe_inventory")
    _require(
        data["sdk_read_source_sha256"] == SDK_READ_SHA256, "unverified_read_source"
    )
    _require(type(data["baud"]) is int and data["baud"] == 1000000, "invalid_baud")
    _require(
        type(data["read_packets_sent"]) is int and data["read_packets_sent"] == 54,
        "incomplete_read_count",
    )
    _require(
        isinstance(data["port"], str) and data["port"].startswith("/dev/"),
        "invalid_port",
    )
    _require(
        isinstance(data["resolved_port"], str)
        and re.fullmatch(r"/dev/tty(?:ACM|USB)[0-9]+", data["resolved_port"]),
        "invalid_port",
    )
    motors = data["motors"]
    _require(isinstance(motors, list) and len(motors) == 9, "incomplete_motor_ids")
    by_id = {}
    for item in motors:
        _require(
            isinstance(item, dict) and _integer(item.get("id"), 1, 9),
            "invalid_motor_id",
        )
        motor_id = item["id"]
        _require(motor_id not in by_id, "duplicate_motor_id")
        registers = item.get("registers")
        _require(
            isinstance(registers, dict) and set(registers) == set(REGISTERS),
            "incomplete_registers",
        )
        raw = {}
        for address, length in REGISTERS.items():
            sample = registers[address]
            _require(
                isinstance(sample, dict) and set(sample) == {"comm", "error", "bytes"},
                "failed_register_read",
            )
            _require(
                type(sample["comm"]) is int
                and sample["comm"] == 0
                and type(sample["error"]) is int
                and sample["error"] == 0,
                "failed_register_read",
            )
            values = sample["bytes"]
            _require(
                isinstance(values, list)
                and len(values) == length
                and all(_integer(v, 0, 255) for v in values),
                "truncated_register_read",
            )
            raw[address] = values
        homing_word = _word(raw["31"])
        _require(
            homing_word <= 0xFFF and homing_word != 0x800, "invalid_homing_sign_bits"
        )
        homing = -(homing_word & 0x7FF) if homing_word & 0x800 else homing_word
        decoded = {
            "id": motor_id,
            "model_number": _word(raw["3"]),
            "operating_mode": raw["33"][0],
            "torque_enabled": raw["40"][0],
            "min_position_limit": _word(raw["9"][:2]),
            "max_position_limit": _word(raw["9"][2:]),
            "homing_offset": homing,
            "position_ticks": _word(raw["56"][:2]),
            "voltage": raw["56"][6] / 10,
            "temperature_c": raw["56"][7],
            "status": raw["56"][9],
        }
        _require(set(item) == {"registers", *decoded}, "invalid_motor_schema")
        for name, value in decoded.items():
            _require(
                type(item[name]) is type(value) and item[name] == value,
                "register_summary_mismatch",
            )
        _require(decoded["model_number"] == 777, "unsupported_motor_model")
        _require(
            decoded["operating_mode"] == (0 if motor_id <= 6 else 1),
            "unexpected_operating_mode",
        )
        _require(
            decoded["torque_enabled"] == 0 and decoded["status"] == 0,
            "unsafe_motor_state",
        )
        low, high = decoded["min_position_limit"], decoded["max_position_limit"]
        _require(
            0 <= low < high <= 4095 and 0 <= decoded["position_ticks"] <= 4095,
            "invalid_position_range",
        )
        if motor_id <= 6:
            _require(
                low <= decoded["position_ticks"] <= high, "arm_outside_saved_range"
            )
        else:
            _require(
                (low, high, homing) == (0, 4095, 0), "unexpected_wheel_calibration"
            )
        by_id[motor_id] = decoded
    _require(set(by_id) == set(range(1, 10)), "incomplete_motor_ids")
    return observed_at, by_id


def _no_links(path):
    for part in (path, *path.parents):
        _require(
            not part.is_symlink() and not getattr(part, "is_junction", lambda: False)(),
            "symlink_path_rejected",
        )


def _read_file(path, limit=512000):
    path = Path(path).absolute()
    _no_links(path)
    _require(path.is_file() and path.stat().st_size <= limit, "invalid_source_file")
    content = path.read_bytes()
    _require(len(content) <= limit, "source_file_too_large")
    return content


def _load_source(root):
    result = {}
    for name, expected in SOURCE_HASHES.items():
        content = _read_file(Path(root) / name, 1024000).replace(b"\r\n", b"\n")
        _require(
            hashlib.sha256(content).hexdigest() == expected, "upstream_contract_changed"
        )
        result[name] = yaml.safe_load(content)
    return result


def validate_candidate(profile, calibration):
    """Enforce disabled writes and the complete pinned wheel-frame contract."""
    _require(
        set(profile)
        == {
            "lekiwi_motor_driver_node",
            "lekiwi_base_controller_node",
            "lekiwi_follower_arm_node",
        },
        "invalid_profile_nodes",
    )
    driver = profile["lekiwi_motor_driver_node"]["ros__parameters"]
    base = profile["lekiwi_base_controller_node"]["ros__parameters"]
    arm = profile["lekiwi_follower_arm_node"]["ros__parameters"]
    for name in ("wheel_write_enabled", "arm_write_enabled"):
        _require(driver.get(name) is False, "unsafe_write_flag")
    _require(
        base.get("enable_motor_write") is False and base.get("torque_enable") is False,
        "unsafe_write_flag",
    )
    _require(
        driver["motor_ids"] == list(range(1, 10))
        and driver["motor_names"] == list(ARM_NAMES + WHEEL_NAMES),
        "invalid_profile_motor_ids",
    )
    _require(
        driver["wheel_ids"] == [7, 8, 9] and driver["arm_ids"] == list(range(1, 7)),
        "invalid_profile_motor_ids",
    )
    _require(
        all(
            base.get(name) == value and type(base.get(name)) is type(value)
            for name, value in WHEEL_CONTRACT.items()
        ),
        "mixed_wheel_contract",
    )
    _require(
        all(type(direction) is float for direction in base["wheel_directions"]),
        "mixed_wheel_contract",
    )
    _require(arm.get("rest_pose_ticks") == "", "unverified_rest_pose")
    _require(set(calibration) == set(ARM_NAMES), "invalid_calibration_joints")
    for number, name in enumerate(ARM_NAMES, 1):
        entry = calibration[name]
        _require(
            set(entry)
            == {"id", "drive_mode", "homing_offset", "range_min", "range_max"},
            "invalid_motor_calibration",
        )
        _require(
            _integer(entry["id"], 1, 6)
            and entry["id"] == number
            and type(entry["drive_mode"]) is int
            and entry["drive_mode"] == 0,
            "invalid_motor_calibration",
        )
        _require(
            _integer(entry["homing_offset"], -2047, 2047)
            and _integer(entry["range_min"])
            and _integer(entry["range_max"])
            and entry["range_min"] < entry["range_max"],
            "invalid_motor_calibration",
        )


def _publish_directory(staging, output):
    # POSIX rename() can overwrite an existing empty directory. NOREPLACE is
    # required so a concurrent creator also retains its directory untouched.
    if os.name == "nt":
        os.rename(staging, output)
    elif sys.platform.startswith("linux"):
        rename = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
        _require(rename is not None, "atomic_publish_unsupported")
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(staging), -100, os.fsencode(output), 1):
            error = ctypes.get_errno()
            if error in (errno.EEXIST, errno.ENOTEMPTY):
                raise FileExistsError("output_already_exists")
            raise OSError(error, "atomic_publish_failed")
    else:
        raise ProfileError("atomic_publish_unsupported")


def prepare_profile(
    inventory, output, *, serial_device, robot_id=None, upstream_root=None
):
    content = _read_file(inventory)
    try:
        data = json.loads(content)
    except (ValueError, UnicodeError):
        raise ProfileError("invalid_inventory_json") from None
    observed_at, motors = validate_inventory(data)
    digest = hashlib.sha256(content).hexdigest()
    robot_id = "eeprom-" + digest[:16] if robot_id is None else robot_id
    _require(
        isinstance(robot_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,40}", robot_id),
        "invalid_robot_id",
    )
    _require(
        isinstance(serial_device, str)
        and re.fullmatch(r"/dev/serial/by-id/[A-Za-z0-9_.:+-]+", serial_device)
        and PurePosixPath(serial_device).name not in (".", ".."),
        "invalid_serial_device",
    )
    root = (
        upstream_root
        or Path(__file__).resolve().parents[2] / "lekiwi_ws"
    )
    source = _load_source(root)
    base = dict(
        source[next(iter(SOURCE_HASHES))]["lekiwi_base_controller_node"][
            "ros__parameters"
        ]
    )
    base.update(
        source["src/lekiwi_description/config/base_frame.yaml"][
            "lekiwi_base_controller_node"
        ]["ros__parameters"]
    )
    base.update(
        source["src/lekiwi_bringup/config/robot_profile.yaml"][
            "lekiwi_base_controller_node"
        ]["ros__parameters"]
    )
    base.update(enable_motor_write=False, torque_enable=False)
    driver = dict(
        source["src/lekiwi_motor/lekiwi_motor_driver/config/lekiwi_motor_driver.yaml"][
            "lekiwi_motor_driver_node"
        ]["ros__parameters"]
    )
    driver.update(
        port=serial_device,
        baud_rate=data["baud"],
        wheel_write_enabled=False,
        arm_write_enabled=False,
    )
    arm = dict(
        source["src/lekiwi_lerobot/config/follower_arm.yaml"][
            "lekiwi_follower_arm_node"
        ]["ros__parameters"]
    )
    arm.update(
        robot_id=robot_id,
        calibration_dir=f"~/xlerobot-shared/device-profiles/{robot_id}/calibration",
        rest_pose_ticks="",
    )
    profile = {
        name: {"ros__parameters": value}
        for name, value in (
            ("lekiwi_motor_driver_node", driver),
            ("lekiwi_base_controller_node", base),
            ("lekiwi_follower_arm_node", arm),
        )
    }
    calibration = {
        name: {
            "id": number,
            "drive_mode": 0,
            "homing_offset": motors[number]["homing_offset"],
            "range_min": motors[number]["min_position_limit"],
            "range_max": motors[number]["max_position_limit"],
        }
        for number, name in enumerate(ARM_NAMES, 1)
    }
    validate_candidate(profile, calibration)
    files = {
        "robot_profile.yaml": yaml.safe_dump(
            profile, sort_keys=False, allow_unicode=True
        ),
        f"calibration/{robot_id}.json": json.dumps(
            calibration, indent=2, ensure_ascii=False
        )
        + "\n",
    }
    manifest = {
        "schema_version": 1,
        "kind": "lekiwi_read_only_device_candidate",
        "prepared_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "inventory": {
            "schema": "guarded_motor_read_preflight_v1",
            "sha256": digest,
            "observed_at": observed_at,
            "source_clock_verified": False,
            "time_basis": "unverified source clock; original inventory timestamp is preserved",
            "sdk_read_source_sha256": SDK_READ_SHA256,
            "raw_registers_decoded_and_summary_checked": True,
            "read_packets": 54,
        },
        "robot_id": robot_id,
        "arm_count": 1,
        "serial_device": serial_device,
        "deployment_directory": f"~/xlerobot-shared/device-profiles/{robot_id}",
        "upstream_contract": {
            "repository": "roboseasy/lekiwi_ws",
            "commit": UPSTREAM_COMMIT,
            "files_sha256_normalized_lf": dict(SOURCE_HASHES),
            "wheel_model": copy.deepcopy(WHEEL_CONTRACT),
        },
        "calibration": {
            "kind": "current_eeprom_snapshot",
            "joints": list(ARM_NAMES),
            "drive_mode": 0,
            "drive_mode_source": "roboseasy/lekiwi_web_operator@48f298c71dd54277e8086a58300703ffee1dbb8e:follower_calibration.calibration_from_registers",
            "physical_calibration_verified": False,
            "rest_pose_ticks": None,
        },
        "verification": {
            "physical_direction_verified": False,
            "physical_motion_verified": False,
            "geometry_confirmed": False,
            "encoder_scale_verified": False,
        },
        "unknown_geometry": {
            "footprint": None,
            "body_dimensions": None,
            "arm_outer_extent": None,
            "lidar_transform": None,
            "imu_transform": None,
        },
        "launch_flags": {
            name: False
            for name in (
                "use_motors",
                "use_base_controller",
                "use_arm",
                "use_lidar",
                "use_imu",
                "use_zmq_host",
                "use_camera",
            )
        },
        "launch_policy": "candidate only; bringup launch arguments can override profile write flags; do not activate without a separate reviewed launch configuration",
        "files": {
            name: hashlib.sha256(text.encode("utf8")).hexdigest()
            for name, text in files.items()
        },
    }
    files["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    output = Path(output).absolute()
    _no_links(output)
    _require(not output.exists(), "output_already_exists")
    _require(output.parent.is_dir(), "output_parent_missing")
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for name, text in files.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
        # Round-trip the on-disk files before publishing the complete directory.
        validate_candidate(
            yaml.safe_load((staging / "robot_profile.yaml").read_text(encoding="utf8")),
            json.loads(
                (staging / f"calibration/{robot_id}.json").read_text(encoding="utf8")
            ),
        )
        for name, expected in manifest["files"].items():
            _require(
                hashlib.sha256((staging / name).read_bytes()).hexdigest() == expected,
                "output_hash_mismatch",
            )
        _publish_directory(staging, output)
    finally:
        if staging.exists():
            # Only remove the temporary directory made in the checked parent.
            _require(
                staging.parent == output.parent
                and staging.name.startswith(f".{output.name}.")
                and not staging.is_symlink(),
                "unsafe_cleanup_target",
            )
            shutil.rmtree(staging)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--serial-device",
        required=True,
        help="Explicit verified /dev/serial/by-id path",
    )
    parser.add_argument(
        "--robot-id", help="New calibration name; otherwise derived from inventory hash"
    )
    parser.add_argument(
        "--upstream-root",
        type=Path,
        help="Pinned lekiwi_ws source; default is sibling upstream-review checkout",
    )
    args = parser.parse_args()
    try:
        manifest = prepare_profile(
            args.inventory,
            args.output,
            serial_device=args.serial_device,
            robot_id=args.robot_id,
            upstream_root=args.upstream_root,
        )
    except (ProfileError, OSError, yaml.YAMLError):
        parser.exit(
            2,
            "Profile preparation rejected; check inventory, pinned source and NEW output directory.\n",
        )
    print(f"Prepared read-only candidate {manifest['robot_id']} in {args.output}")


if __name__ == "__main__":
    main()
