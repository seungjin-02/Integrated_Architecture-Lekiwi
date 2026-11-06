// Explicit synthetic Alert fixtures; these fixed values are not live evaluations.
export const response={
  "count": 13,
  "limit": 13,
  "alerts": [
    {
      "alert_id": 13,
      "trace_id": "demo-trace-13",
      "created_at": "2026-11-02T13:10:00+09:00",
      "event_id": "demo-event-13",
      "level": "CRITICAL",
      "risk_score": 4,
      "uncertainty_score": 0,
      "human_required": true,
      "recommended_actions": [
        "stop_and_clear_obstacle",
        "check_lidar_orientation_and_footprint",
        "verify_stop_before_resuming"
      ],
      "reason_summary": "collision risk detected: obstacle 0.08 m ahead while moving forward at 0.08 m/s",
      "signals": [
        {
          "rule_id": "robot_demo_collision_imminent",
          "category": "risk",
          "score": 4,
          "reason": "forward motion detected with obstacle clearance of 0.08 m",
          "evidence": {
            "obstacle_distance_m": 0.08,
            "forward_speed_mps": 0.08,
            "stop_confirmed": false
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 12,
      "trace_id": "demo-trace-12",
      "created_at": "2026-11-02T13:00:00+09:00",
      "event_id": "demo-event-12",
      "level": "CRITICAL",
      "risk_score": 4,
      "uncertainty_score": 0,
      "human_required": true,
      "recommended_actions": [
        "halt_operation_and_keep_area_clear",
        "cut_power_if_wheel_motion_persists",
        "inspect_motor_controller_and_driver"
      ],
      "reason_summary": "stop failure detected: wheel motion persists 2000 ms after stop command",
      "signals": [
        {
          "rule_id": "robot_demo_stop_failure",
          "category": "risk",
          "score": 4,
          "reason": "encoder reports wheel motion after stop command",
          "evidence": {
            "elapsed_since_stop_ms": 2000,
            "wheel_speed_mps": 0.06,
            "stop_confirmed": false
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 11,
      "trace_id": "demo-trace-11",
      "created_at": "2026-11-02T12:10:00+09:00",
      "event_id": "demo-event-11",
      "level": "WARN",
      "risk_score": 1,
      "uncertainty_score": 0,
      "human_required": true,
      "recommended_actions": [
        "pause_control_and_reduce_link_distance",
        "check_wifi_signal_and_interference"
      ],
      "reason_summary": "control link degraded: response latency 1200 ms and packet loss 15 percent",
      "signals": [
        {
          "rule_id": "robot_demo_control_latency",
          "category": "risk",
          "score": 1,
          "reason": "control response latency 1200 ms; packet loss 15 percent",
          "evidence": {
            "response_latency_ms": 1200,
            "packet_loss_percent": 15
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 10,
      "trace_id": "demo-trace-10",
      "created_at": "2026-11-02T12:00:00+09:00",
      "event_id": "demo-event-10",
      "level": "WARN",
      "risk_score": 1,
      "uncertainty_score": 0,
      "human_required": true,
      "recommended_actions": [
        "finish_operation_and_return_to_charge",
        "check_power_and_charging_connection"
      ],
      "reason_summary": "battery low: remaining charge 18 percent",
      "signals": [
        {
          "rule_id": "robot_demo_battery_low",
          "category": "risk",
          "score": 1,
          "reason": "battery charge remaining: 18 percent",
          "evidence": {
            "battery_percent": 18
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 9,
      "trace_id": "demo-trace-04-03",
      "created_at": "2026-11-02T11:20:00+09:00",
      "event_id": "demo-event-04-03",
      "level": "WARN",
      "risk_score": 1,
      "uncertainty_score": 3,
      "human_required": true,
      "recommended_actions": [
        "check_wheel_feedback_usb_and_power",
        "verify_physical_stop",
        "hold_motion_until_resolved"
      ],
      "reason_summary": "motor feedback missing after command acceptance",
      "signals": [
        {
          "rule_id": "robot_demo_feedback_missing_0",
          "category": "risk",
          "score": 1,
          "reason": "motor feedback not received after command acceptance",
          "evidence": {
            "motor_feedback": null
          },
          "is_critical_override": false
        },
        {
          "rule_id": "robot_demo_motion_state_unknown",
          "category": "uncertainty",
          "score": 3,
          "reason": "motion and stop state unavailable: motor feedback missing; root cause unresolved",
          "evidence": {
            "motion_state": null,
            "stop_state": null
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 8,
      "trace_id": "demo-trace-04-02",
      "created_at": "2026-11-02T11:10:00+09:00",
      "event_id": "demo-event-04-02",
      "level": "CRITICAL",
      "risk_score": 0,
      "uncertainty_score": 1,
      "human_required": true,
      "recommended_actions": [
        "compare_evidence_and_trace_id",
        "reject_evidence_until_integrity_verified"
      ],
      "reason_summary": "motor feedback rejected: evidence signature verification failed",
      "signals": [
        {
          "rule_id": "robot_demo_integrity_failure_0",
          "category": "failure",
          "score": 0,
          "reason": "feedback signature verification failed",
          "evidence": {
            "signature_verified": false
          },
          "is_critical_override": true
        },
        {
          "rule_id": "robot_demo_missing_8_0",
          "category": "uncertainty",
          "score": 1,
          "reason": "robot state unavailable: feedback evidence is not trusted",
          "evidence": {
            "trusted_feedback": null
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 7,
      "trace_id": "demo-trace-04-01",
      "created_at": "2026-11-02T11:00:00+09:00",
      "event_id": "demo-event-04-01",
      "level": "INFO",
      "risk_score": 0,
      "uncertainty_score": 0,
      "human_required": false,
      "recommended_actions": [],
      "reason_summary": "manual drive command accepted",
      "signals": [
        {
          "rule_id": "robot_demo_observation",
          "category": "observation",
          "score": 0,
          "reason": "manual drive command accepted",
          "evidence": {
            "command_status": "accepted"
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 6,
      "trace_id": "demo-trace-03-02",
      "created_at": "2026-11-02T10:10:00+09:00",
      "event_id": "demo-event-03-02",
      "level": "WARN",
      "risk_score": 1,
      "uncertainty_score": 0,
      "human_required": false,
      "recommended_actions": [
        "check_active_control_owner",
        "close_active_session_and_retry"
      ],
      "reason_summary": "autonomous control request rejected: manual control session is active",
      "signals": [
        {
          "rule_id": "robot_demo_control_rejected_0",
          "category": "risk",
          "score": 1,
          "reason": "autonomous request conflicts with active manual control session",
          "evidence": {
            "active_mode": "manual",
            "requested_mode": "autonomous"
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 5,
      "trace_id": "demo-trace-03-01",
      "created_at": "2026-11-02T10:00:00+09:00",
      "event_id": "demo-event-03-01",
      "level": "INFO",
      "risk_score": 0,
      "uncertainty_score": 0,
      "human_required": false,
      "recommended_actions": [],
      "reason_summary": "manual control ownership acquired",
      "signals": [
        {
          "rule_id": "robot_demo_observation",
          "category": "observation",
          "score": 0,
          "reason": "manual control ownership acquired",
          "evidence": {
            "control_mode": "manual"
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 4,
      "trace_id": "demo-trace-02-02",
      "created_at": "2026-11-02T09:10:00+09:00",
      "event_id": "demo-event-02-02",
      "level": "WARN",
      "risk_score": 1,
      "uncertainty_score": 1,
      "human_required": true,
      "recommended_actions": [
        "check_lidar_freshness_and_connection",
        "verify_stop_with_motor_feedback",
        "hold_navigation_until_resolved"
      ],
      "reason_summary": "lidar scan stale: scan age 3200 ms exceeds freshness limit 1000 ms; stop requested",
      "signals": [
        {
          "rule_id": "robot_demo_stale_sensor_0",
          "category": "risk",
          "score": 1,
          "reason": "lidar scan age 3200 ms exceeds freshness limit 1000 ms",
          "evidence": {
            "scan_age_ms": 3200,
            "freshness_limit_ms": 1000
          },
          "is_critical_override": false
        },
        {
          "rule_id": "robot_demo_missing_4_0",
          "category": "uncertainty",
          "score": 1,
          "reason": "stop state unconfirmed: wheel feedback missing",
          "evidence": {
            "stop_feedback": null
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 3,
      "trace_id": "demo-trace-02-01",
      "created_at": "2026-11-02T09:00:00+09:00",
      "event_id": "demo-event-02-01",
      "level": "INFO",
      "risk_score": 0,
      "uncertainty_score": 0,
      "human_required": false,
      "recommended_actions": [],
      "reason_summary": "autonomous navigation start requested",
      "signals": [
        {
          "rule_id": "robot_demo_observation",
          "category": "observation",
          "score": 0,
          "reason": "autonomous navigation start request received",
          "evidence": {
            "requested_mode": "autonomous"
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 2,
      "trace_id": "demo-trace-01-02",
      "created_at": "2026-11-02T08:10:00+09:00",
      "event_id": "demo-event-01-02",
      "level": "INFO",
      "risk_score": 0,
      "uncertainty_score": 0,
      "human_required": false,
      "recommended_actions": [
        "check_sensor_freshness_before_next_run"
      ],
      "reason_summary": "drive command and encoder feedback received",
      "signals": [
        {
          "rule_id": "robot_demo_observation",
          "category": "observation",
          "score": 0,
          "reason": "drive command and encoder feedback recorded",
          "evidence": {
            "encoder_feedback_received": true
          },
          "is_critical_override": false
        }
      ]
    },
    {
      "alert_id": 1,
      "trace_id": "demo-trace-01-01",
      "created_at": "2026-11-02T08:00:00+09:00",
      "event_id": "demo-event-01-01",
      "level": "INFO",
      "risk_score": 0,
      "uncertainty_score": 0,
      "human_required": false,
      "recommended_actions": [],
      "reason_summary": "operation session started",
      "signals": [
        {
          "rule_id": "robot_demo_observation",
          "category": "observation",
          "score": 0,
          "reason": "operation session started",
          "evidence": {
            "session_status": "active"
          },
          "is_critical_override": false
        }
      ]
    }
  ],
  "next_cursor": null
};
