"""Upstream Nav2 pipeline with installation-specific collision envelope."""


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
    import tempfile
    from pathlib import Path

    import yaml
    from ament_index_python.packages import get_package_share_directory
    from launch import LaunchDescription
    from launch.actions import (
        DeclareLaunchArgument,
        IncludeLaunchDescription,
        OpaqueFunction,
        RegisterEventHandler,
    )
    from launch.event_handlers import OnShutdown
    from launch.launch_description_sources import PythonLaunchDescriptionSource
    from launch.substitutions import LaunchConfiguration

    root = _extension_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from xlerobot_web_operator.navigation_adapter import load_navigation_profile, navigation_parameters

    def setup(context):
        profile = load_navigation_profile(
            LaunchConfiguration("navigation_profile").perform(context)
        )
        share = Path(get_package_share_directory("lekiwi_navigation2"))
        params = navigation_parameters(
            yaml.safe_load((share / "config/nav2_params.yaml").read_text()), profile
        )
        with tempfile.NamedTemporaryFile(
            mode="w", prefix="xlerobot-nav-", suffix=".yaml", delete=False
        ) as stream:
            yaml.safe_dump(params, stream)
            path = Path(stream.name)

        def cleanup(_context):
            path.unlink(missing_ok=True)
            return []

        return [
            RegisterEventHandler(
                OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup)])
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    str(share / "launch/navigation.launch.py")
                ),
                launch_arguments={
                    "map": LaunchConfiguration("map"),
                    "params_file": str(path),
                    "operator_nodes": LaunchConfiguration("operator_nodes"),
                }.items(),
            ),
        ]

    return LaunchDescription(
        [
            DeclareLaunchArgument("map"),
            DeclareLaunchArgument("navigation_profile"),
            DeclareLaunchArgument("operator_nodes"),
            OpaqueFunction(function=setup),
        ]
    )
