# LeKiwi 원본·통합형 비교

`main`은 통합에 사용한 로보시지 원본을 보존하는 기준 브랜치입니다. 원본 기능을 수정한 운영 릴리스가 아닙니다.

```text
lekiwi_web_operator/   원본 전문 웹 화면 + Python 제어 엔진
lekiwi_ws/             원본 모터·센서·SLAM·Nav2 ROS 패키지
```

| 원본 | 가져온 커밋 | 파일 수 |
|---|---|---|
| [웹 제어센터](https://github.com/roboseasy/lekiwi_web_operator) | `48f298c71dd54277e8086a58300703ffee1dbb8e` | 73 |
| [ROS workspace](https://github.com/roboseasy/lekiwi_ws) | `7ea3da19dee975c34907677f40e823c256fbefdb` | 238 |

원본 파일의 내용·경로·실행 권한을 유지합니다. 파일별 기준은 [UPSTREAM.lock.json](UPSTREAM.lock.json)에 있습니다.
이 잠금 파일은 출처와 동일성 확인용이며 새 라이선스를 부여하지 않습니다. 원본 주석·출처·패키지별 라이선스·제3자 고지를 유지합니다.

통합형 브랜치/PR에서는 같은 두 폴더에 확장만 추가합니다. GitHub의 Files changed에서 원본을 직접 수정했는지와 추가 파일을 비교할 수 있습니다.

원본 사용법: [웹 제어센터 README](lekiwi_web_operator/README.md) · [ROS workspace README](lekiwi_ws/README.md)
