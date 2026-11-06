"""Explicit launcher for ONE original native engine with optional event hooks.

Running this starts the normal native server/ROS engine. It is never called by
the selector, collector, preview, or tests automatically. Stop any other
native engine first. Only a versionchecked prepared COPY is accepted.
"""

import argparse
import importlib
import logging
import os
import signal
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from observability.hooks import HookEmitter, NativeObservedService
from xlerobot_web_operator.native_event_hooks import verify_prepared


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-source", required=True, type=Path)
    parser.add_argument(
        "--wheel-only-profile",
        type=Path,
        help="Opt-in prepared wheel-only device candidate; no arm/sensor launch",
    )
    parser.add_argument(
        "--navigation-profile",
        type=Path,
        help="Opt-in commissioned SLAM/Nav2 installation; requires wheel-only-profile",
    )
    parser.add_argument(
        "--enable-native-calibration",
        action="store_true",
        help="Expose original follower calibration; never starts a calibration automatically",
    )
    parser.add_argument("--web-config", required=True, type=Path,
                        help="Camera/device configuration for the shared web server")
    parser.add_argument("--observer-port", type=int, default=18095)
    parser.add_argument("--library", type=Path,
                        default=Path.home()/'.local/share/xlerobot-mobile/library.json')
    parser.add_argument("--event-endpoint", default="http://127.0.0.1:18095/api/ingest")
    parser.add_argument(
        "--spool-dir", type=Path, default=Path("private/native-event-spool")
    )
    parser.add_argument(
        "native_args",
        nargs=argparse.REMAINDER,
        help="After --: original --host/--port/--read-only options",
    )
    args = parser.parse_args(argv)
    try:
        source = verify_prepared(args.native_source)
    except (OSError, ValueError):
        parser.exit(
            1,
            "Unsupported or unprepared native source; prepare and review an explicit copy first.\n",
        )
    if args.enable_native_calibration and not args.wheel_only_profile:
        parser.error("--enable-native-calibration requires --wheel-only-profile")
    if args.navigation_profile and not args.wheel_only_profile:
        parser.error("--navigation-profile requires --wheel-only-profile")
    if args.navigation_profile:
        from xlerobot_web_operator.navigation_adapter import load_navigation_profile

        load_navigation_profile(args.navigation_profile)
    if args.wheel_only_profile:
        os.environ["XLEROBOT_SOURCE_ROOT"] = str(ROOT)
    token = os.environ.get("XLEROBOT_EVENT_TOKEN", "")
    if not token:
        parser.error("Set XLEROBOT_EVENT_TOKEN; no default credential is provided")
    # No import or launch of native ROS code occurs during module import/help.
    sys.path.insert(0, str(source))
    native = importlib.import_module("lekiwi_web_operator.__main__")
    if not Path(native.__file__).resolve().is_relative_to(source):
        parser.exit(
            1,
            "A different native package is already imported; use a fresh Python process.\n",
        )
    from observability.transport import DurableSink

    native_args = (
        args.native_args[1:] if args.native_args[:1] == ["--"] else args.native_args
    )
    original_args = native._parse_args(native_args)
    if args.wheel_only_profile:
        config = importlib.import_module("lekiwi_web_operator.config")
        if args.navigation_profile:
            from xlerobot_web_operator.navigation_adapter import install_command_adapter

            install_command_adapter(
                config,
                args.wheel_only_profile,
                args.navigation_profile,
                calibration_mode=args.enable_native_calibration,
            )
        else:
            from xlerobot_web_operator.wheel_only_adapter import install_command_adapter

            install_command_adapter(
                config,
                args.wheel_only_profile,
                calibration_mode=args.enable_native_calibration,
            )
    from xlerobot_web_operator.shared_http import make_request_handler
    config = importlib.import_module("lekiwi_web_operator.config")
    request_handler = make_request_handler(args.web_config, map_dir=config.map_dir(),
                                          library=args.library, observer_port=args.observer_port)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    stop = threading.Event()
    saved_signals = {}
    sink = emitter = robot = None
    try:
        # Normal signal semantics are preserved, with portable SIGHUP handling.
        for number in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGHUP", None)):
            if number is None or (
                number == getattr(signal, "SIGHUP", None)
                and signal.getsignal(number) is signal.SIG_IGN
            ):
                continue
            saved_signals[number] = signal.getsignal(number)
            signal.signal(number, lambda _number, _frame: stop.set())
        sink = DurableSink(args.spool_dir, args.event_endpoint, token)
        emitter = HookEmitter(sink.submit)
        service = native.RobotService(original_args.read_only)
        if args.wheel_only_profile:
            from xlerobot_web_operator.wheel_only_adapter import WheelOnlyService

            wrapper = WheelOnlyService
            if args.navigation_profile:
                from xlerobot_web_operator.navigation_adapter import NavigationService

                wrapper = NavigationService
            service = wrapper(service, allow_calibration=args.enable_native_calibration)
        robot = NativeObservedService(service, emitter)
        return native._serve(robot, original_args, stop, request_handler=request_handler)
    finally:
        try:
            if robot is not None:
                robot.shutdown()
        finally:
            if emitter is not None:
                emitter.close()
            if sink is not None:
                sink.close()
            for number, handler in saved_signals.items():
                signal.signal(number, handler)


if __name__ == "__main__":
    raise SystemExit(main())
