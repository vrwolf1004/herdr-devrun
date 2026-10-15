# 사용법

## 1. 설치

요구 사항:
- herdr 0.9.0 이상
- Python 3.8 이상, 외부 패키지 없음. Windows는 `python`, Linux/macOS는 `python3`가 PATH에 있어야 한다.

### GitHub에서 설치

```sh
herdr plugin install vrwolf1004/herdr-devrun
herdr plugin list                                 # herdr-devrun 이 enabled 인지 확인
```

- 업데이트는 같은 명령을 다시 실행한다. 특정 버전 고정은 `--ref <태그 또는 커밋>`을 붙인다.
- 빌드 단계가 없어서 내려받은 파일을 그대로 쓴다.

### 로컬 폴더로 등록 (개발용)

```sh
herdr plugin link C:\work\app\herdr-devrun   # Linux/macOS 는 clone 한 경로
```

- `link`는 폴더를 복사하지 않고 그대로 등록한다. 파일을 고치면 다음 실행부터 바로 반영된다.
- `herdr-plugin.toml`을 고쳤다면(액션 추가 등) `unlink` 후 다시 `link` 한다.

### 관리

- 해제: `herdr plugin unlink herdr-devrun`(link) / `herdr plugin uninstall herdr-devrun`(install)
- 일시 중지: `herdr plugin disable herdr-devrun` / 다시 사용: `herdr plugin enable herdr-devrun`

## 표시 언어

대시보드와 알림 문구는 `en`, `ko`, `ru`, `fr`, `es`, `de`, `ja`를 지원한다. 언어 결정 우선순위는 다음과 같다.

1. 환경변수 `HERDR_DEVRUN_LANG`
2. 플러그인 설정 파일 `HERDR_PLUGIN_CONFIG_DIR/config.json`의 `"lang"` 값
3. OS 언어(Windows는 사용자 UI 언어, Linux/macOS는 `LC_ALL`, `LC_MESSAGES`, `LANG` 순서)
4. 기본값 `en` (OS 언어를 지원하지 않거나 확인할 수 없을 때)

예를 들어 `HERDR_DEVRUN_LANG=ko`로 설정하면 한글 문구를 사용한다. `ko-KR`, `ko_KR.UTF-8` 같은 로케일 표기도 인식한다. 환경변수나 플러그인 설정을 지정하면 OS 언어보다 우선하며, 번역에 없는 문구는 영어 번역으로 대체한다.

### 액션 id

herdr는 액션 id 중복을 허용하지 않는다. 그래서 OS별 실행기(`python` / `python3`)에 맞춰 같은 동작을 두 번 선언하고 Windows 쪽 id에 `-windows`를 붙였다(herdr-file-viewer, herdr-sidebar와 같은 관례). 이 문서는 Linux/macOS id로 쓴다. **Windows에서는 뒤에 `-windows`를 붙인다.**

| Linux / macOS | Windows | 기능 |
|---|---|---|
| `herdr-devrun.init` | `herdr-devrun.init-windows` | 설정 파일 초안 만들기 |
| `herdr-devrun.up` | `herdr-devrun.up-windows` | 서비스 띄우기 |
| `herdr-devrun.run` | `herdr-devrun.run-windows` | 서비스 띄우기(`up`과 같은 동작, 아직 `herdr-plugin.toml`에는 없음) |
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
      "env": { "SPRING_PROFILES_ACTIVE": "local" },
      "stop_timeout": 20
    },
    {
      "name": "frontend",
      "cwd": "frontend",
      "command": "npm run dev",
      "port": 5173,
      "url": "http://localhost:5173",
      "depends_on": ["backend"]
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
| `services[].port` | | 서비스가 여는 TCP 포트. "시작 중"과 "실행 중"을 구분하고, 시작 전에 이미 쓰이고 있으면 시작하지 않는다 |
| `services[].url` | | 대시보드 "브라우저" 버튼(`o`)으로 열 주소 |
| `services[].depends_on` | | 먼저 준비돼야 하는 서비스 이름 목록. 전체 시작(`up`, 대시보드 `a`)에서 순서를 정한다 (5장) |
| `services[].start_timeout` | | `depends_on`이 준비되기를 기다리는 최대 초. 기본 120 |
| `services[].stop_timeout` | | 중지할 때 Ctrl+C 후 프로세스가 끝나기를 기다리는 최대 초. 기본 10 |

작성 요령:
- JSON 문자열 안의 `\`는 `\\`로, `"`는 `\"`로 쓴다. 예: `".\\gradlew.bat bootRun"`
- 여러 명령은 `;`로 잇는다(PowerShell, bash, zsh 공통). 예: `"pnpm install; pnpm run dev"`
- OS마다 명령이 다르면 `command`에 한쪽을, `command_windows` 또는 `command_unix`에 다른 쪽을 쓴다. 같으면 `command`만 쓴다.
- 암호화 키, 비밀번호 같은 비밀값은 `env`에 적지 않는다. OS 환경변수로 두면 pane이 물려받는다. 설정 파일은 git에 올라갈 수 있다.
- 설정 파일을 팀과 공유하지 않으려면 프로젝트 `.gitignore`에 `.herdr-devrun.json`을 추가한다.
- 설정 검증: 숫자가 아닌 `stop_timeout`/`start_timeout`, 없는 서비스를 가리키는 `depends_on`, 순환(`a → b → a`, 자기 자신 포함)은 오류로 알려 준다.

> **보안 주의**: `command`는 그대로 셸에 입력된다. 남의 저장소를 받아 `up`을 실행하면 그 저장소가 정한 명령이 실행된다(npm scripts, Makefile과 같은 성격). 처음 받은 저장소는 실행 전에 `.herdr-devrun.json` 내용을 확인한다.

## 5. 실행과 중지

| 하고 싶은 것 | 액션 | 동작 |
|---|---|---|
| 서비스 띄우기 | `up` (또는 `run`, 추가 예정 별칭) | 안 떠 있는 서비스를 `depends_on` 순서대로 탭에 실행. 모두 떠 있으면 그 탭으로 이동 |
| 서비스 내리기 | `down` | 각 pane에 Ctrl+C → 프로세스가 끝나면(최대 `stop_timeout`) 탭 닫기 |
| 다시 띄우기 | `restart` | down 후 up. 설정 파일을 고친 뒤 반영할 때도 쓴다 |

- 액션은 실행한 pane의 폴더에서 **위로 올라가며** 설정 파일을 찾는다. 프로젝트 안의 하위 폴더에서 실행해도 된다.
- `up`은 안 떠 있는 서비스만 띄운다. 일부만 떠 있으면 나머지를 같은 탭에 추가한다.
- 서비스 하나만 다루려면 대시보드(6장)를 쓴다.
- 탭이나 pane을 손으로 닫아도 된다. 다음 실행 때 사라진 것을 확인하고 상태를 정리한다.

### 실행 순서 (`depends_on`)

- 의존 서비스가 **준비되면** 시작한다. 준비 기준: `port`가 있으면 그 포트가 열림(다른 곳에서 띄운 서버여도 인정), 없으면 "실행 중".
- 의존 서비스가 끝나 버리면(✕ 종료됨) 기다리던 서비스는 "의존 서비스 실패"로 시작하지 않는다. 막 띄운 서비스는 5초 동안 실패로 보지 않는다.
- `start_timeout`(기본 120초)이 지나도 준비되지 않으면 "대기 시간 초과"로 시작하지 않는다.
- 시작하지 못한 서비스는 이유와 함께 알림(대시보드는 아래 줄)으로 보여 준다. 예: `web (dependency failed), late (timed out waiting for dependencies)`
- 대시보드에서 서비스 **하나**를 시작할 때는 직접 고른 것이므로 의존 서비스를 기다리지 않는다.

### 포트 충돌

- `port`를 이미 다른 프로세스가 쓰고 있으면 그 서비스는 시작하지 않는다. 띄워도 포트 충돌로 실패하는데, 포트는 열려 있어 "실행 중"으로 잘못 보이기 때문이다.
- 전체 시작에서는 그 서비스만 건너뛰고(`port in use`) 나머지는 시작한다.

### 중지 대기

- Ctrl+C를 보낸 뒤 pane 셸 아래 프로세스가 끝날 때까지 0.2초 간격으로 확인하고, 끝나면 바로 pane/탭을 닫는다. `stop_timeout`(기본 10초)이 지나면 그대로 닫는다(남은 프로세스는 pane과 함께 종료).
- Spring Boot graceful shutdown처럼 오래 걸리는 서비스는 `stop_timeout`을 늘린다.
- Windows `.bat`가 Ctrl+C 후 "일괄 작업을 끝내시겠습니까 (Y/N)?"를 묻는 상태는 이미 끝난 것으로 본다.

## 6. 대시보드

`panel` 액션을 실행하면 현재 pane 오른쪽에 대시보드 pane이 열린다. 서비스 탭과는 별개의 pane이라, 작업하던 탭에서 서비스를 보면서 조작할 수 있다. 같은 프로젝트의 대시보드가 이미 열려 있으면 새로 열지 않고 그쪽으로 이동한다.

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
| ◔ 대기 중 | 전체 시작에서 `depends_on`을 기다리는 중 | |
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

- 한/영 상태가 한글이어도 단축키가 동작한다(ㄱ=r, ㅁ=a, ㅌ=x, ㅐ=o, ㄷ=e, ㅂ=q).
- 상태와 로그 미리보기는 1초마다 갱신된다. 로그는 선택한 서비스 pane의 최근 출력이며, pane 폭에서 접힌 줄도 원래 한 줄로 보여 준다.
- 전체 시작은 기다리는 동안에도 선택·스크롤 같은 입력을 받는다. 진행 중에 전체 중지를 누르면 남은 시작을 취소한다.
- 서비스가 많아 화면을 넘으면 선택한 행을 따라 목록이 스크롤되고, 위아래에 `▲ n more` / `▼ n more`가 보인다.
- 폭이 좁으면 40칸 미만에서 포트 열을, 30칸 미만에서 상태 이름을 숨기고 아이콘만 보인다.
- 예상하지 못한 오류가 나도 대시보드는 닫히지 않고 아래 줄에 요약을 보여 준다. 자세한 내용은 상태 폴더의 `panel.log`에 남는다.
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
