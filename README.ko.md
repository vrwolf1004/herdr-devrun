# herdr-devrun

[English](README.md) | [**한국어**](README.ko.md)

지원 언어: 영어 · 한국어 · 러시아어 · 프랑스어 · 스페인어 · 독일어 · 일본어

프로젝트 개발 서비스를 하나의 herdr 대시보드에서 별도 pane으로 실행하고 관리합니다.

## 대시보드 디자인

서비스 상태, 포트, 최근 로그를 확인합니다. 서비스 줄마다 시작/중지, 수정, 삭제, 닫기 버튼이 있습니다. 하단 버튼 줄에는 전체 시작, 전체 중지, 브라우저, + 추가가 있고, 하단 줄 오른쪽에는 `Ctrl+H 도움말`이 표시됩니다. 공유 `devrun` space 안의 프로젝트 탭에서 서비스 왼쪽에 열립니다.

```text
 ▣ devrun · my-project                                  2/3 실행

   상태       서비스                                     포트
 ▸ ● 실행 중  backend                                    :8080     ■ 중지   ✎ 수정   ✕ 삭제   ⊗
   ◐ 시작 중  frontend                                   :5173
   ○ 중지     worker

  전체 시작   전체 중지   브라우저   + 추가

─ 로그 · backend ──────────────────────────────────────────────
 Started Application in 4.2 seconds
                                                 Ctrl+H 도움말
```

`Ctrl+H`를 누르면 대시보드 위에 도움말 팝업이 뜹니다. 아무 키나 누르거나 클릭하면 닫힙니다:

```text
        ╭────────────────────────────────────────╮
        │             Ctrl+H 도움말              │
        ├────────────────────────────────────────┤
        │ ↑ ↓  서비스 선택                       │
        │ Enter  시작 / 중지                     │
        │ Ctrl+S  전체 시작   Ctrl+X  전체 중지  │
        │ Ctrl+R  전체 재시작   Ctrl+O  브라우저 │
        │ Ctrl+E  설정   Ctrl+L  언어            │
        │ Ctrl+C  종료                           │
        ╰────────────────────────────────────────╯
```

### 키

| 키 | 기능 |
| --- | --- |
| `↑` `↓` | 서비스 선택 |
| `Enter` | 선택한 서비스 시작 또는 중지 |
| `Ctrl+S` | 전체 시작 |
| `Ctrl+X` | 전체 중지 |
| `Ctrl+R` | 전체 재시작 (중지 후 시작) |
| `Ctrl+O` | 선택한 서비스 브라우저 열기 |
| `Ctrl+E` | 설정 열기 |
| `Ctrl+L` | 언어 바꾸기: 시스템 → 영어 → … → 일본어 → 시스템 (`config.json`에 저장) |
| `Ctrl+H` | 도움말 팝업 열기/닫기 |
| `Ctrl+C` | 대시보드 닫고 셸로 돌아가기 |

이 플러그인은 Agents 사이드바 블록 대신 프로젝트 대시보드를 사용합니다.

## 설치

```sh
herdr plugin install vrwolf1004/herdr-devrun
```

## 액션

| 액션 | 기능 |
| --- | --- |
| `up` | 실행 중이 아닌 서비스를 `depends_on` 순서대로 시작 |
| `run` | `up`과 같은 서비스 시작 동작 |
| `down` | 서비스를 중지하고 프로젝트 탭을 닫기 (남은 탭이 없으면 `devrun` space도 닫기) |
| `restart` | 서비스를 중지한 뒤 다시 시작 |
| `panel` | 프로젝트 대시보드 열기 |
| `init` | `.herdr-devrun.json` 초안 만들기 |

Windows에서는 각 액션 ID 뒤에 `-windows`를 붙입니다. 설정과 예시는 [사용법](docs/usage.ko.md)을 참고하세요.

`run`은 별도의 herdr 액션 ID이며 `up`과 같은 방식으로 서비스를 시작합니다.
프로젝트 설정이 유효하지 않으면 액션 오류로 보고합니다. herdr가 새 서비스 명령을
pane에 입력하지 못하면 새 탭과 저장 상태를 정리하고, 기존 탭에서는 새로 추가한
pane만 닫습니다. 검증 항목과 오류 복구는 [사용법](docs/usage.ko.md)을 참고하세요.

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
- [추가 항목](docs/readme-extras.ko.md): README에서 옮긴 항목

## 프로젝트 응원하기

프로젝트가 도움이 되셨다면 커피 한 잔으로 개발을 응원해 주세요.

[![Ko-fi에서 응원하기](https://img.shields.io/badge/Ko--fi-%EC%9D%91%EC%9B%90%ED%95%98%EA%B8%B0-FF5E5B?style=for-the-badge&logo=buymeacoffee&logoColor=white)](https://ko-fi.com/dev_ohyt)
