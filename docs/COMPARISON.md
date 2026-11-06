# 원본과 추가 코드 비교

| 위치 | 통합형에서 달라진 점 |
|---|---|
| `lekiwi_web_operator/lekiwi_web_operator/http_server.py` | 요청 처리 클래스 선택 인자 추가. 기본값은 원본 클래스 |
| `lekiwi_web_operator/lekiwi_web_operator/__main__.py` | 서버 생성에 선택 인자 전달. 원본 실행·종료 절차 유지 |
| 나머지 원본 엔진·로보시지 UI·ROS 패키지 | 변경 없음 |
| `web/mobile/` | 모바일 조작·지도·미션 화면. 원본 API/WS 직접 사용 |
| `xlerobot_web_operator/shared_http.py` | 같은 서버에 모바일 파일·진단·지도 부가 API·로그 조회 경로 추가 |
| `xlerobot_web_operator/run_native_observed.py` | 단일 엔진·웹 확장·이벤트 Hook 조립 |
| `xlerobot_web_operator/*adapter.py`, `launch/` | 실제 기기 프로필·ROS 실행 연결 |
| `observability/`, `web/monitor/` | 독립 이벤트 수집·spool·SQLite·조회와 대시보드 |
| `runtime/` | 엔진·선택 화면·Collector 실행 템플릿. 별도 모바일 서비스 없음 |
