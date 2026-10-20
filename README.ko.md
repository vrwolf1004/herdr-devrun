# herdr-devrun

[English](README.md) | **한국어**

프로젝트의 개발 서비스를 하나의 herdr 대시보드에서 각각의 pane으로 실행하고 관리하는 플러그인입니다.

- Windows, Linux, macOS 지원
- Python 3.8 이상, 표준 라이브러리만 사용
- herdr 0.9.0 이상

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

## 설치

```sh
herdr plugin install vrwolf1004/herdr-devrun
```

프로젝트에 `.herdr-devrun.json`을 작성한 뒤 액션이나 대시보드에서 서비스를 관리하세요. `init` 액션은 초안 파일을 만들어 줍니다.

## 액션

| 액션 | 하는 일 |
| --- | --- |
| `up` | 실행 중이 아닌 서비스를 `depends_on` 순서대로 시작합니다 |
| `down` | 각 서비스에 Ctrl+C를 보내고, 종료될 때까지 기다린 뒤(최대 `stop_timeout`) 탭을 닫습니다 |
| `restart` | 서비스를 다시 시작합니다 |
| `panel` | 대시보드를 엽니다 (프로젝트마다 하나) |
| `init` | 현재 폴더에 `.herdr-devrun.json` 초안을 만듭니다 |

Windows에서는 각 액션 id 뒤에 `-windows`를 붙입니다.

```sh
herdr plugin action invoke up-windows --plugin herdr-devrun   # windows
herdr plugin action invoke up --plugin herdr-devrun           # linux / macos
```

- 7개 언어 지원: 영어, 한국어, 러시아어, 프랑스어, 스페인어, 독일어, 일본어

## 문서

- [설치, 설정, 액션 및 대시보드 사용법](docs/usage.ko.md)
- [Usage guide (English)](docs/usage.md)
- [문제 해결](docs/troubleshooting.md)
- [개발과 테스트](docs/development.md)
- [구조 및 동작 방식](docs/architecture.md)
- [만든 이유와 범위](docs/start-idea.md)

## 개발

```sh
python -m unittest discover -s tests
```

## 라이선스

[MIT](LICENSE)

---

## 프로젝트 응원하기

프로젝트가 도움이 되셨다면 커피 한 잔으로 개발을 응원해 주세요.

[![Ko-fi에서 응원하기](https://img.shields.io/badge/Ko--fi-%EC%9D%91%EC%9B%90%ED%95%98%EA%B8%B0-FF5E5B?style=for-the-badge&logo=buymeacoffee&logoColor=white)](https://ko-fi.com/dev_ohyt)
