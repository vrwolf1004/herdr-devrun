# 사용법

## 1. 설치

요구 사항:
- herdr 0.9.0 이상
- Python 3.8 이상, 외부 패키지 없음. Windows는 `python`, Linux/macOS는 `python3`가 PATH에 있어야 한다.

### GitHub에서 설치

```sh
herdr plugin install vrwolf1004/herdrPlugin-devrun
herdr plugin list                                 # herdr-devrun 이 enabled 인지 확인
```

- 업데이트는 같은 명령을 다시 실행한다. 특정 버전 고정은 `--ref <태그 또는 커밋>`을 붙인다.
- 빌드 단계가 없어서 내려받은 파일을 그대로 쓴다.

### 로컬 폴더로 등록 (개발용)

```sh
herdr plugin link C:\work\app\herdrPlugin-devrun   # Linux/macOS 는 clone 한 경로
```

- `link`는 폴더를 복사하지 않고 그대로 등록한다. 파일을 고치면 다음 실행부터 바로 반영된다.
- `herdr-plugin.toml`을 고쳤다면(액션 추가 등) `unlink` 후 다시 `link` 한다.

### 관리

- 해제: `herdr plugin unlink herdr-devrun`(link) / `herdr plugin uninstall herdr-devrun`(install)
- 일시 중지: `herdr plugin disable herdr-devrun` / 다시 사용: `herdr plugin enable herdr-devrun`

### 액션 id

herdr는 액션 id 중복을 허용하지 않는다. 그래서 OS별 실행기(`python` / `python3`)에 맞춰 같은 동작을 두 번 선언하고 Windows 쪽 id에 `-windows`를 붙였다(herdr-file-viewer, herdr-sidebar와 같은 관례). 이 문서는 Linux/macOS id로 쓴다. **Windows에서는 뒤에 `-windows`를 붙인다.**

| Linux / macOS | Windows | 기능 |
|---|---|---|
| `herdr-devrun.init` | `herdr-devrun.init-windows` | 설정 파일 초안 만들기 |
| `herdr-devrun.up` | `herdr-devrun.up-windows` | 서비스 띄우기 |
| `herdr-devrun.down` | `herdr-devrun.down-windows` | 서비스 내리기 |
| `herdr-devrun.restart` | `herdr-devrun.restart-windows` | 다시 띄우기 |
| `herdr-devrun.panel` | `herdr-devrun.panel-windows` | 대시보드 열기 |

## 2. 단축키 연결

herdr `config.toml`(Windows: `%APPDATA%\herdr\config.toml`)에 추가한다. 아래는 Windows 예시이며, Linux/macOS는 `-windows`를 뺀다.

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

```sh
herdr config check          # ok 확인
herdr server reload-config  # 실행 중인 서버에 반영
```

- 키를 정하기 전에 기존 바인딩이나 다른 플러그인 키와 겹치지 않는지 확인한다.
- 단축키 없이 실행: `herdr plugin action invoke herdr-devrun.up` (지금 포커스된 pane 기준)

## 3. 프로젝트에 설정 파일 만들기

1. herdr에서 프로젝트 루트 폴더로 이동한 pane을 하나 연다.
2. `init` 액션을 실행한다.
3. 프로젝트 루트에 `.herdr-devrun.json`이 생긴다. 알림에 감지한 서비스 수가 표시된다.
4. 파일을 열어 명령, 폴더, 포트, 환경변수를 실제 실행 방법에 맞게 고친다.

`init` 감지 규칙 (루트와 바로 아래 폴더, 폴더마다 첫 번째로 맞는 하나):

| 발견한 파일 | 만들어지는 명령 (Windows / Linux·macOS) |
|---|---|
| `gradlew.bat` 또는 `gradlew` | `.\gradlew.bat bootRun` / `./gradlew bootRun` |
| `mvnw.cmd` 또는 `mvnw` | `.\mvnw.cmd spring-boot:run` / `./mvnw spring-boot:run` |
| `package.json` (`dev` / `start` / `serve` 스크립트) | `pnpm` / `yarn` / `npm run <script>` (lock 파일 기준) |

- `init`은 지금 OS에 맞는 명령을 `command`에 넣는다. 여러 OS에서 같은 설정 파일을 쓰려면 `command_windows` / `command_unix`를 추가한다(4장).
- Gradle/Maven 서비스에는 Spring Boot 기본값 `port: 8080`, `url: http://localhost:8080`을 함께 넣는다. 실제 포트와 다르면 고친다.
- 멀티 모듈 Gradle이나 pnpm 모노레포처럼 루트에서 특정 앱을 지정해야 하는 경우는 감지 결과를 직접 고친다.

## 4. 설정 파일 형식

```json
{
  "tab": "my-project",
  "services": [
    {
      "name": "backend",
      "cwd": "backend",
      "command": "./gradlew bootRun",
      "command_windows": ".\\gradlew.bat bootRun",
      "port": 8080,
      "url": "http://localhost:8080",
      "env": { "SPRING_PROFILES_ACTIVE": "local" }
    },
    {
      "name": "frontend",
      "cwd": "frontend",
      "command": "npm run dev",
      "port": 5173,
      "url": "http://localhost:5173"
    }
  ]
}
```

| 항목 | 필수 | 설명 |
|---|---|---|
| `tab` | | 탭 이름. 없으면 프로젝트 폴더 이름 |
| `services` | O | 1개 이상. 순서대로 pane에 배치된다 |
| `services[].name` | O | pane 이름. 알림과 상태 파일에도 쓰여 중복되면 안 된다 |
| `services[].command` | O | pane 셸에 그대로 입력할 명령 (Windows: PowerShell, Linux/macOS: 기본 셸) |
| `services[].command_windows` | | Windows에서 `command` 대신 쓸 명령 |
| `services[].command_unix` | | Linux/macOS에서 `command` 대신 쓸 명령 |
| `services[].cwd` | | 설정 파일 기준 상대 경로 (절대 경로도 가능). 없으면 프로젝트 루트. 폴더가 없으면 오류 |
| `services[].env` | | pane 프로세스에 넣을 환경변수 (`"KEY": "VALUE"`) |
| `services[].port` | | 서비스가 여는 TCP 포트. 대시보드가 이 포트로 "시작 중"과 "실행 중"을 구분한다 |
| `services[].url` | | 대시보드 "브라우저" 버튼(`o`)으로 열 주소 |

작성 요령:
- JSON 문자열 안의 `\`는 `\\`로, `"`는 `\"`로 쓴다. 예: `".\\gradlew.bat bootRun"`
- 여러 명령은 `;`로 잇는다(PowerShell, bash, zsh 공통). 예: `"pnpm install; pnpm run dev"`
- OS마다 명령이 다르면 `command`에 한쪽을, `command_windows` 또는 `command_unix`에 다른 쪽을 쓴다. 같으면 `command`만 쓴다.
- 암호화 키, 비밀번호 같은 비밀값은 `env`에 적지 않는다. OS 환경변수로 두면 pane이 물려받는다. 설정 파일은 git에 올라갈 수 있다.
- 설정 파일을 팀과 공유하지 않으려면 프로젝트 `.gitignore`에 `.herdr-devrun.json`을 추가한다.

## 5. 실행과 중지

| 하고 싶은 것 | 액션 | 동작 |
|---|---|---|
| 서비스 띄우기 | `up` | 안 떠 있는 서비스를 탭에 실행. 모두 떠 있으면 그 탭으로 이동 |
| 서비스 내리기 | `down` | 각 pane에 Ctrl+C → 1.5초 후 탭 닫기 |
| 다시 띄우기 | `restart` | down 후 up. 설정 파일을 고친 뒤 반영할 때도 쓴다 |

- 액션은 실행한 pane의 폴더에서 **위로 올라가며** 설정 파일을 찾는다. 프로젝트 안의 하위 폴더에서 실행해도 된다.
- `up`은 안 떠 있는 서비스만 띄운다. 일부만 떠 있으면 나머지를 같은 탭에 추가한다.
- 서비스 하나만 다루려면 대시보드(6장)를 쓴다.
- 탭이나 pane을 손으로 닫아도 된다. 다음 실행 때 사라진 것을 확인하고 상태를 정리한다.

## 6. 대시보드

`panel` 액션을 실행하면 현재 pane 오른쪽에 대시보드 pane이 열린다. 서비스 탭과는 별개의 pane이라, 작업하던 탭에서 서비스를 보면서 조작할 수 있다.

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

### 상태

| 표시 | 의미 | 판단 기준 |
|---|---|---|
| ● 실행 중 | 동작 중 | pane 셸 아래에 실행 중인 프로세스가 있고, `port`가 열려 있음 (`port`가 없으면 프로세스만 확인) |
| ◐ 시작 중 | 뜨는 중 | 프로세스는 있지만 `port`가 아직 안 열림 |
| ✕ 종료됨 | 명령이 끝남 | pane은 있지만 셸만 남음. 실패했거나 끝난 경우라 로그를 확인한다 |
| ○ 중지 | 안 떠 있음 | pane 없음 |
| … 처리 중 | 대시보드가 시작·중지하는 중 | |

### 조작

| 하고 싶은 것 | 마우스 | 키 |
|---|---|---|
| 서비스 선택 | 행 클릭, 휠 | `↑` `↓` `Home` `End` |
| 선택한 서비스 시작/중지 | 행 더블클릭, `▶ 시작`/`■ 중지` 버튼 | `Enter` |
| 선택한 서비스 재시작 | `↻ 재시작` 버튼 | `r` |
| 전체 시작 / 전체 중지 | 버튼 | `a` / `x` |
| 브라우저로 열기 (`url`) | `브라우저` 버튼 | `o` |
| 설정 파일 열기 | `설정` 버튼 | `e` |
| 대시보드 닫기 | `닫기` 버튼 | `q`, `Esc`, `Ctrl+C` |

- 상태와 로그 미리보기는 1초마다 갱신된다. 로그는 선택한 서비스 pane의 최근 출력이다.
- 설정 파일을 저장하면 자동으로 다시 읽는다. 형식이 틀리면 아래 줄에 오류를 띄우고 이전 설정을 유지한다.
- 설정 파일은 OS 기본 프로그램으로 연다(Windows: 연결 프로그램, 없으면 메모장 / macOS: `open` / Linux: `xdg-open`).
- 서비스 하나를 중지하면 그 pane만 닫는다. 마지막 서비스를 중지하면 서비스 탭도 닫는다.
- 재시작은 pane을 닫고 새로 연다. Windows의 `gradlew.bat` 같은 배치 파일은 Ctrl+C 후 "일괄 작업을 끝내시겠습니까?"를 묻기 때문에, 같은 pane에서 다시 실행하지 않는다.
- 대시보드를 닫아도 서비스는 계속 돈다.

## 7. 예시

### Spring Boot (Gradle 멀티 모듈) + React (pnpm 모노레포)

```json
{
  "tab": "office-dev",
  "services": [
    {
      "name": "BE manager",
      "cwd": "office-be",
      "command": "./gradlew :app-manager:bootRun",
      "command_windows": ".\\gradlew.bat :app-manager:bootRun",
      "port": 5002,
      "env": { "SPRING_PROFILES_ACTIVE": "local" }
    },
    {
      "name": "FE manager",
      "cwd": "office-fe",
      "command": "pnpm --filter @office/web-manager run dev",
      "port": 6000,
      "url": "http://localhost:6000"
    }
  ]
}
```

### 백엔드 여러 개 + 프론트 하나

```json
{
  "services": [
    { "name": "api",   "cwd": "api",   "command": "./mvnw spring-boot:run", "command_windows": ".\\mvnw.cmd spring-boot:run", "port": 8080 },
    { "name": "batch", "cwd": "batch", "command": "./mvnw spring-boot:run", "command_windows": ".\\mvnw.cmd spring-boot:run", "port": 8081 },
    { "name": "web",   "cwd": "web",   "command": "npm run dev", "port": 5173 }
  ]
}
```

배치: `api`는 왼쪽, 오른쪽에는 위에서부터 `batch`, `web` 순서로 놓인다.

### Spring Boot 인자 넘기기

```json
{ "name": "api", "command": "./gradlew bootRun --args=\"--server.port=8081\"", "port": 8081 }
```

## 8. 수동 실행 (herdr 액션 없이)

```sh
# 플러그인 폴더에서. Windows 는 python, Linux/macOS 는 python3
python -X utf8 src/devrun.py up --dir <프로젝트 폴더>     # up / down / restart / init
python -X utf8 src/panel.py --dir <프로젝트 폴더>         # 대시보드를 지금 터미널에서 바로 실행
```

- 코드를 고친 뒤 확인하거나, 액션이 실패한 원인을 콘솔에서 바로 볼 때 쓴다. herdr CLI가 서버에 연결해야 하므로 herdr 안의 pane에서 실행한다.
- 수동 실행 상태는 Windows `%LOCALAPPDATA%\herdr-devrun`, Linux/macOS `~/.local/state/herdr-devrun`(또는 `$XDG_STATE_HOME/herdr-devrun`)에 저장된다. 액션 실행 상태(`HERDR_PLUGIN_STATE_DIR`)와 따로 관리되므로, 수동으로 띄운 것은 수동 `down`으로 내린다.
