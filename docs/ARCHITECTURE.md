# 하나의 서버·엔진, 두 화면

```mermaid
flowchart TD
 S[선택 화면 :8091] --> M[모바일 :8080/mobile/]
 S --> W[로보시지 UI :8080/]
 M --> H[같은 HTTP 서버 · API · WebSocket]
 W --> H
 H --> E[단일 Native Engine · 제어권 · 안전 정책]
 E --> R[원본 ROS · 모터 · 센서 · SLAM · Nav2]
 E -.관측 이벤트.-> Q[비차단 Hook · Durable spool]
 Q -.HTTP.-> C[독립 Collector :18095]
 C --> D[SQLite 원본 이력]
 D --> O[로그 화면 :8080/monitor/]
```

## 실행 흐름

1. 사용자가 `:8091`에서 화면을 선택합니다.
2. 두 화면은 `:8080`의 `/ws`에 직접 연결하고 원본 Hub에서 client_id를 받습니다.
3. 같은 출처의 POST는 원본 HTTP 검사와 단일 엔진의 제어권·안전 정책을 거칩니다.
4. 연결 종료와 제어권 해제는 원본 Hub가 처리합니다.
5. 엔진 이벤트는 비차단 Hook → spool → Collector → SQLite로 별도 수집됩니다.
