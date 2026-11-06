#!/usr/bin/env bash
# Engine startup only. No bringup, torque, calibration or mission is started here.
set -eo pipefail
: "${ROS_WORKSPACE_SETUP:?Set the existing ROS workspace setup.bash path}"
: "${XLEROBOT_NATIVE_SOURCE:?Set the hash-verified prepared Native source copy}"
: "${XLEROBOT_WHEEL_PROFILE:?Set the verified device candidate robot_profile.yaml}"
: "${XLEROBOT_EVENT_TOKEN:?Set the private collector transport token}"
source /opt/ros/jazzy/setup.bash
source "$ROS_WORKSPACE_SETUP"
runtime_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../lekiwi_web_operator" && pwd)"
cd "$runtime_root"
export PYTHONPATH="$runtime_root${PYTHONPATH:+:$PYTHONPATH}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}" ROS_LOCALHOST_ONLY=1
args=(--web-config "${XLEROBOT_WEB_CONFIG:-$HOME/.config/lekiwi/mobile.json}" --native-source "$XLEROBOT_NATIVE_SOURCE" --wheel-only-profile "$XLEROBOT_WHEEL_PROFILE")
if [[ -n "${XLEROBOT_NAVIGATION_PROFILE:-}" ]]; then
    args+=(--navigation-profile "$XLEROBOT_NAVIGATION_PROFILE")
fi
exec python3 -m xlerobot_web_operator "${args[@]}" --spool-dir "$HOME/.local/share/lekiwi/event-spool" -- --host 0.0.0.0 --port 8080
