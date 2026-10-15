# herdr-devrun

프로젝트의 개발 서비스(백엔드, 프론트엔드 등)를 herdr 탭 하나에 pane 별로 띄우는 herdr 로컬 플러그인입니다. 서비스 목록은 프로젝트 루트의 `.herdr-devrun.json`에 적고, 대시보드 pane에서 마우스·키보드로 시작·중지·재시작합니다.

- Windows / Linux / macOS
- Python 3.8 이상, 표준 라이브러리만 사용 (Windows: `python`, Linux/macOS: `python3`가 PATH에 있어야 함)
- herdr 0.9.0 이상

자세한 문서:
- [docs/start-idea.md](docs/start-idea.md): 만든 이유, 제약, 범위
- [docs/usage.md](docs/usage.md): 설치, 단축키, 설정 파일 작성, 대시보드, 예시
- [docs/architecture.md](docs/architecture.md): 모듈 구조, 실행 흐름, 상태 판정, OS별 처리, 구현 메모
- [docs/troubleshooting.md](docs/troubleshooting.md): 증상별 원인과 해결, 수정 후 확인 방법

## 설치

```sh
herdr plugin install vrwolf1004/herdrPlugin-devrun
herdr plugin action list --plugin herdr-devrun
```

빌드 단계가 없어 내려받은 파일을 그대로 씁니다. 업데이트는 같은 명령을 다시 실행하고, 제거는 `herdr plugin uninstall herdr-devrun`입니다.

개발할 때는 clone 한 폴더를 그대로 등록합니다 (파일을 고치면 바로 반영):

```sh
git clone https://github.com/vrwolf1004/herdrPlugin-devrun.git
herdr plugin link <clone 한 경로>
```

## 액션

herdr는 액션 id 중복을 허용하지 않아, Windows용 id에는 `-windows`가 붙습니다 (herdr-file-viewer, herdr-sidebar와 같은 관례).

| Linux / macOS | Windows | 기능 |
|---|---|---|
| `herdr-devrun.init` | `herdr-devrun.init-windows` | 현재 pane 폴더(와 바로 아래 폴더)를 보고 `.herdr-devrun.json` 초안 생성 |
| `herdr-devrun.up` | `herdr-devrun.up-windows` | 안 떠 있는 서비스를 탭에 실행. 모두 떠 있으면 그 탭으로 이동 |
| `herdr-devrun.down` | `herdr-devrun.down-windows` | 각 pane에 Ctrl+C를 보낸 뒤 탭을 닫음 |
| `herdr-devrun.restart` | `herdr-devrun.restart-windows` | down 후 up |
| `herdr-devrun.panel` | `herdr-devrun.panel-windows` | 옆에 **대시보드 pane** 열기 |

액션은 **실행한 pane의 폴더에서 위로 올라가며** `.herdr-devrun.json`을 찾습니다. 결과와 오류는 herdr 알림으로 표시됩니다.

## 대시보드

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

- 상태: ● 실행 중 / ◐ 시작 중(`port` 대기) / ✕ 종료됨(명령이 끝남) / ○ 중지 / … 처리 중
- 마우스: 행 클릭 선택, 행 더블클릭 시작·중지, 버튼 클릭, 휠로 선택 이동
- 키: `↑↓` 선택, `Enter` 시작·중지, `r` 재시작, `a` 전체 시작, `x` 전체 중지, `o` 브라우저, `e` 설정 열기, `q`/`Esc` 닫기
- 선택한 서비스의 로그 끝부분을 1초마다 갱신하고, 설정 파일을 저장하면 자동으로 다시 읽습니다.

## 단축키 (herdr `config.toml`)

Windows 예시입니다. Linux/macOS는 `-windows`를 빼고 씁니다.

```toml
[[keys.command]]
key = "prefix+r"
type = "plugin_action"
command = "herdr-devrun.up-windows"
description = "devrun: start services"

[[keys.command]]
key = "prefix+d"
type = "plugin_action"
command = "herdr-devrun.panel-windows"
description = "devrun: dashboard"

[[keys.command]]
key = "prefix+shift+r"
type = "plugin_action"
command = "herdr-devrun.down-windows"
description = "devrun: stop services"
```

추가 후 `herdr config check` → `herdr server reload-config`. 기존 키와 겹치지 않는지 먼저 확인하세요.

## 설정 파일 (`.herdr-devrun.json`)

```json
{
  "tab": "my-project",
  "services": [
    {
      "name": "backend",
      "cwd": "backend",
      "command": "./gradlew :app-api:bootRun",
      "command_windows": ".\\gradlew.bat :app-api:bootRun",
      "port": 8080,
      "url": "http://localhost:8080/swagger-ui.html",
      "env": { "SPRING_PROFILES_ACTIVE": "local" }
    },
    { "name": "frontend", "cwd": "frontend", "command": "pnpm --filter web run dev", "port": 5173, "url": "http://localhost:5173" }
  ]
}
```

| 항목 | 필수 | 설명 |
|---|---|---|
| `tab` | | 탭 이름. 없으면 프로젝트 폴더 이름 |
| `services[].name` | O | pane 이름 (중복 불가) |
| `services[].command` | O | pane 셸에 입력할 명령 |
| `services[].command_windows` / `command_unix` | | 해당 OS에서 `command` 대신 쓸 명령 |
| `services[].cwd` | | 설정 파일 기준 상대 경로. 없으면 프로젝트 루트 |
| `services[].env` | | pane 프로세스에 넣을 환경변수 |
| `services[].port` | | 이 포트가 열리면 "실행 중", 아니면 "시작 중" |
| `services[].url` | | 대시보드 "브라우저" 버튼으로 열 주소 |

배치: 첫 서비스는 왼쪽, 두 번째는 오른쪽, 세 번째부터는 오른쪽 아래로 쌓입니다. 암호화 키 같은 비밀값은 `env`에 적지 말고 OS 환경변수로 두세요.

## 수동 실행 / 디버깅

```sh
python src/devrun.py up --dir <프로젝트 폴더>      # Linux/macOS 는 python3
python src/panel.py --dir <프로젝트 폴더>          # 대시보드를 지금 터미널에서
herdr plugin log list --plugin herdr-devrun       # 액션 실행 결과(stderr) 확인
```

실행 상태(탭/pane id)는 herdr가 주는 `HERDR_PLUGIN_STATE_DIR`에 저장합니다. 수동 실행 시에는 Windows `%LOCALAPPDATA%\herdr-devrun`, Linux/macOS `~/.local/state/herdr-devrun`을 쓰므로, 수동으로 띄운 것은 수동으로 내려야 합니다.

## 주의

- `down`과 서비스 중지는 Ctrl+C 후 1.5초 기다렸다가 pane/탭을 닫습니다. 닫히면 pane 안의 프로세스도 종료됩니다.
- Linux/macOS 경로(입력 처리, 프로세스 조회)는 코드와 단위 테스트까지만 확인했고, 실제 herdr 환경에서는 아직 실행해 보지 않았습니다.
