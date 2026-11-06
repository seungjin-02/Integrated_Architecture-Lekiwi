// Presentation translations only. Unknown system text is preserved verbatim.
import {summaryFor as baseSummaryFor,signalReason as baseSignalReason} from './display-contract.js';
const summaryLabels=Object.freeze({
  "collision risk detected: obstacle 0.08 m ahead while moving forward at 0.08 m/s": "충돌 위험 · 전방 8cm 장애물에도 전진 중입니다.",
  "stop failure detected: wheel motion persists 2000 ms after stop command": "정지 실패 · 정지 명령 2초 후에도 바퀴가 회전합니다.",
  "control link degraded: response latency 1200 ms and packet loss 15 percent": "제어 통신 지연 · 명령 응답에 1.2초가 걸립니다.",
  "battery low: remaining charge 18 percent": "배터리 부족 · 잔량 18%, 충전이 필요합니다.",
  "motor feedback missing after command acceptance": "모터 피드백 수신 실패 · 명령 접수 후 모터 응답이 없습니다.",
  "motor feedback rejected: evidence signature verification failed": "모터 피드백 신뢰 불가 · 수신 데이터의 서명이 일치하지 않습니다.",
  "manual drive command accepted": "조종 요청 접수",
  "autonomous control request rejected: manual control session is active": "자율주행 요청 거부 · 다른 세션이 수동 제어권을 사용 중입니다.",
  "manual control ownership acquired": "수동 조종 권한 획득",
  "lidar scan stale: scan age 3200 ms exceeds freshness limit 1000 ms; stop requested": "LiDAR 갱신 중단 · 스캔 지연 3,200ms로 정지를 요청했습니다.",
  "autonomous navigation start requested": "자율주행 시작 요청 수신",
  "drive command and encoder feedback received": "주행 피드백 수신 · 주행 명령과 엔코더 피드백이 기록됐습니다.",
  "operation session started": "운영 세션 시작"
});
const reasonLabels=Object.freeze({
  "motion and stop state unavailable: motor feedback missing; root cause unresolved": "모터 피드백 누락으로 이동·정지 상태와 원인을 확인할 수 없음",
  "forward motion detected with obstacle clearance of 0.08 m": "전방 장애물과의 거리 8cm, 전진 속도 0.08m/s",
  "encoder reports wheel motion after stop command": "정지 명령 이후에도 엔코더에서 바퀴 회전 감지",
  "control response latency 1200 ms; packet loss 15 percent": "명령 응답 지연 1,200ms, 패킷 손실 15%",
  "battery charge remaining: 18 percent": "배터리 잔량 18%",
  "motor feedback not received after command acceptance": "명령 이후 모터 피드백이 도착하지 않음",
  "feedback signature verification failed": "증거 서명 검증 실패",
  "robot state unavailable: feedback evidence is not trusted": "해당 증거로 로봇 상태를 판단할 수 없음",
  "manual drive command accepted": "조종 요청 접수",
  "autonomous request conflicts with active manual control session": "상충하는 제어 요청 관측",
  "manual control ownership acquired": "수동 조종 권한 획득",
  "lidar scan age 3200 ms exceeds freshness limit 1000 ms": "LiDAR 데이터 갱신 중단: 3,200ms",
  "stop state unconfirmed: wheel feedback missing": "정지 후 바퀴 피드백이 없어 실제 정지를 확인할 수 없음",
  "autonomous navigation start request received": "자율주행 시작 요청 수신",
  "drive command and encoder feedback recorded": "주행 명령과 엔코더 피드백이 함께 기록됐습니다.",
  "operation session started": "운영 세션 시작"
});
export const actionLabels=Object.freeze({
  "stop_and_clear_obstacle": "즉시 정지하고 장애물과의 간격을 확보하세요.",
  "check_lidar_orientation_and_footprint": "LiDAR 방향과 로봇 외곽 설정을 확인하세요.",
  "verify_stop_before_resuming": "정지 동작을 점검한 뒤 운행을 재개하세요.",
  "halt_operation_and_keep_area_clear": "로봇 주변 접근을 막고 주행을 중단하세요.",
  "cut_power_if_wheel_motion_persists": "바퀴가 멈추지 않으면 전원을 차단하세요.",
  "inspect_motor_controller_and_driver": "모터 제어와 드라이버 상태를 점검하세요.",
  "pause_control_and_reduce_link_distance": "조종을 멈추고 로봇과 접속 기기의 거리를 줄이세요.",
  "check_wifi_signal_and_interference": "Wi-Fi 신호와 주변 간섭을 확인하세요.",
  "finish_operation_and_return_to_charge": "운행을 마무리하고 충전 위치로 복귀하세요.",
  "check_power_and_charging_connection": "전원과 충전 연결 상태를 확인하세요.",
  "check_wheel_feedback_usb_and_power": "바퀴 피드백과 USB·전원 상태를 확인하세요.",
  "verify_physical_stop": "현장에서 실제 정지를 확인하세요.",
  "hold_motion_until_resolved": "해결 전 추가 주행을 시작하지 마세요.",
  "compare_evidence_and_trace_id": "원본 증거와 Trace ID를 대조하세요.",
  "reject_evidence_until_integrity_verified": "무결성이 확인될 때까지 해당 증거를 사용하지 마세요.",
  "check_active_control_owner": "현재 제어권 소유자를 확인하세요.",
  "close_active_session_and_retry": "기존 세션 종료 후 원하는 모드에서 다시 요청하세요.",
  "check_lidar_freshness_and_connection": "LiDAR 데이터 갱신 상태와 연결을 확인하세요.",
  "verify_stop_with_motor_feedback": "모터 피드백으로 실제 정지를 확인하세요.",
  "hold_navigation_until_resolved": "문제가 해결되기 전 자율주행을 재개하지 마세요.",
  "check_sensor_freshness_before_next_run": "다음 운행 전 센서 갱신 상태를 확인하세요."
});
export function summaryFor(alert){return Object.hasOwn(summaryLabels,alert.reason_summary)?summaryLabels[alert.reason_summary]:baseSummaryFor(alert);}
export function signalReason(signal){return Object.hasOwn(reasonLabels,signal.reason)?reasonLabels[signal.reason]:baseSignalReason(signal);}
