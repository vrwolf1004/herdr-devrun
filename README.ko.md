# herdr-devrun

[English](README.md) | [**한국어**](README.ko.md)

지원 언어: 영어 · 한국어 · 러시아어 · 프랑스어 · 스페인어 · 독일어 · 일본어

프로젝트 개발 서비스를 하나의 herdr 대시보드에서 별도 pane으로 실행하고 관리합니다.

## 대시보드 디자인

서비스 상태, 포트, 최근 로그를 확인하고 서비스를 시작·중지·재시작하거나 URL을 열 수 있습니다. 현재 pane 오른쪽에 열리며 Ctrl+C를 누르면 셸로 돌아옵니다.

```text
 ▣ devrun · my-project                                  2/3 실행

   상태       서비스                                     포트
 ▸ ● 실행 중  backend                                    :8080
   ◐ 시작 중  frontend                                   :5173
   ○ 중지     worker

  ■ 중지   ↻ 재시작   전체 시작   전체 중지   브라우저   설정   닫기

─ 로그 · backend ──────────────────────────────────────────────
 Started Application in 4.2 seconds
```

이 플러그인은 Agents 사이드바 블록 대신 프로젝트 대시보드를 사용합니다.

## 설치

```sh
herdr plugin install vrwolf1004/herdr-devrun
```

## 액션

| 액션 | 기능 |
| --- | --- |
| `up` | 실행 중이 아닌 서비스를 `depends_on` 순서대로 시작 |
| `down` | 서비스를 중지하고 서비스 탭 닫기 |
| `restart` | 서비스를 중지한 뒤 다시 시작 |
| `panel` | 프로젝트 대시보드 열기 |
| `init` | `.herdr-devrun.json` 초안 만들기 |

Windows에서는 각 액션 ID 뒤에 `-windows`를 붙입니다. 설정과 예시는 [사용법](docs/usage.ko.md)을 참고하세요.

## 요구 사항

- Windows, Linux, macOS
- herdr 0.9.0 이상
- Python 3.8 이상, 표준 라이브러리만 사용

## 문서

- [사용법 (한국어)](docs/usage.ko.md)
- [Usage (English)](docs/usage.md)
- [문제 해결](docs/troubleshooting.md)
- [구조 및 동작 방식](docs/architecture.md)
- [개발과 테스트](docs/development.md)
- [만든 이유와 범위](docs/start-idea.md)
- [할 일](docs/todo.md)

## 개발

```sh
python -m unittest discover -s tests
```

## 라이선스

[MIT](LICENSE)

## 프로젝트 응원하기

프로젝트가 도움이 되셨다면 커피 한 잔으로 개발을 응원해 주세요.

[![Ko-fi에서 응원하기](https://img.shields.io/badge/Ko--fi-%EC%9D%91%EC%9B%90%ED%95%98%EA%B8%B0-FF5E5B?style=for-the-badge&logo=buymeacoffee&logoColor=white)](https://ko-fi.com/dev_ohyt)
