# LeKiwi 통합형 운영

로보시지 Native 엔진 하나와 웹 서버 하나를 로보시지 UI·XLeRobot 모바일 UI가 공유합니다.

| 폴더 | 역할 |
|---|---|
| `lekiwi_web_operator/lekiwi_web_operator/` | 원본 제어 엔진·API·안전 정책 |
| `lekiwi_web_operator/web/` | 로보시지·모바일·로그 화면 |
| `lekiwi_web_operator/xlerobot_web_operator/` | 웹 확장·기기 어댑터·실행 조립 |
| `lekiwi_web_operator/observability/` | 이벤트 수집·SQLite·조회 |
| `lekiwi_ws/src/` | 원본 ROS·모터·센서·SLAM·Nav2 |
| `runtime/` | 서비스·실행 설정 |
| `docs/` | 아키텍처·원본 비교 |

선택 화면 `:8091` → 모바일 `:8080/mobile/` 또는 로보시지 UI `:8080/`. 양쪽 모두 같은 `/api/`와 `/ws`를 직접 사용합니다.

[아키텍처](docs/ARCHITECTURE.md) · [원본과 차이](docs/COMPARISON.md)

## 수정한 원본 코드

파일 경로 기준: `lekiwi_web_operator/lekiwi_web_operator/`

| 파일 | 원본 main 줄 | 현재 PR 줄 | 수정 내용 |
|---|---|---|---|
| [__main__.py](lekiwi_web_operator/lekiwi_web_operator/__main__.py#L63) | 63 | 63 | `_serve`에 선택적 `request_handler` 인자 추가 |
| [__main__.py](lekiwi_web_operator/lekiwi_web_operator/__main__.py#L72-L73) | 72 | 72–73 | 확장 요청 처리기를 서버 생성 시 전달 |
| [http_server.py](lekiwi_web_operator/lekiwi_web_operator/http_server.py#L434) | 433 뒤에 추가 | 434 | 요청 처리 클래스 선택 인자 추가. 기본값은 원본 클래스 |
| [http_server.py](lekiwi_web_operator/lekiwi_web_operator/http_server.py#L442) | 441 | 442 | 선택된 클래스로 HTTP 서버 초기화 |

## 원본 기준

로보시지 [웹 엔진](https://github.com/roboseasy/lekiwi_web_operator) `48f298c`와 [ROS 워크스페이스](https://github.com/roboseasy/lekiwi_ws) `7ea3da1`가 기준입니다.

</details>
