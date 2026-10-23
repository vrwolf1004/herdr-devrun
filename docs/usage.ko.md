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
| `herdr-devrun.run` | `herdr-devrun.run-windows` | 서비스 띄우기(`up`과 같은 동작) |
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
- 단축키 없이 실행: `herdr plugin action invoke up --plugin herdr-devrun` 또는 `herdr plugin action invoke run --plugin herdr-devrun` (Windows: `up-windows` 또는 `run-windows`). 두 액션 모두 현재 포커스된 pane의 프로젝트를 사용한다.
- `run`은 `up`과 같은 시작 구현을 호출하는 별도 액션 ID다. `run`은 별도의 CLI 하위 명령이 아니다.

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
- 설정 파일은 프로젝트 루트나, 액션을 실행하는 폴더의 위쪽 어느 폴더에 두어도 된다. `.run` 폴더에 두는 것은 한 가지 예시일 뿐 필수가 아니다.
- JSON 문자열 안의 `\`는 `\\`로, `"`는 `\"`로 쓴다. 예: `".\\gradlew.bat bootRun"`
- 여러 명령은 `;`로 잇는다(PowerShell, bash, zsh 공통). 예: `"pnpm install; pnpm run dev"`
- OS마다 명령이 다르면 `command`에 한쪽을, `command_windows` 또는 `command_unix`에 다른 쪽을 쓴다. 같으면 `command`만 쓴다.
- 암호화 키, 비밀번호 같은 비밀값은 `env`에 적지 않는다. OS 환경변수로 두면 pane이 물려받는다. 설정 파일은 git에 올라갈 수 있다.
- 설정 파일을 팀과 공유하지 않으려면 프로젝트 `.gitignore`에 `.herdr-devrun.json`을 추가한다.
- 설정 검증: 최상위 값은 JSON 객체여야 하고 `services`는 비어 있지 않은 목록이어야
  한다. 각 서비스에는 중복되지 않는 `name`과 명령이 필요하다. `port`는 1~65535의
  정수, `start_timeout`/`stop_timeout`은 0 이상의 숫자여야 한다. `depends_on`은
  존재하는 서비스 이름 목록이어야 하며, 순환(자기 자신 포함)은 오류로 보고한다.
  잘못된 설정은 파일 경로와 검증 오류를 포함해 액션 오류로 표시한다.

> **보안 주의**: `command`는 그대로 셸에 입력된다. 남의 저장소를 받아 `up`을 실행하면 그 저장소가 정한 명령이 실행된다(npm scripts, Makefile과 같은 성격). 처음 받은 저장소는 실행 전에 `.herdr-devrun.json` 내용을 확인한다.

## 5. 실행과 중지

| 하고 싶은 것 | 액션 | 동작 |
|---|---|---|
| 서비스 띄우기 | `up` (또는 `run`, 같은 액션) | 안 떠 있는 서비스를 `depends_on` 순서대로 탭에 실행. 모두 떠 있으면 그 탭으로 이동 |
| 서비스 내리기 | `down` | 각 pane에 Ctrl+C → 프로세스가 끝나면(최대 `stop_timeout`) 프로젝트 탭을 닫고, 남은 탭이 없으면 `devrun` space도 닫기 |
| 다시 띄우기 | `restart` | down 후 up. 설정 파일을 고친 뒤 반영할 때도 쓴다 |

- 액션은 실행한 pane의 폴더에서 **위로 올라가며** 설정 파일을 찾는다. 프로젝트 안의 하위 폴더에서 실행해도 된다.
- `up`은 안 떠 있는 서비스만 띄운다. 일부만 떠 있으면 나머지를 같은 탭에 추가한다.
- 대시보드에서 시작(시작 버튼 또는 `a`)해도 같은 규칙이다. 컨트롤 박스가 없으면 먼저 `devrun` space에 만들고, 만들 수 없으면 아무것도 띄우지 않고 오류를 보인다. 재시작은 아직 이 규칙을 따르지 않는다.
- 서비스 하나만 다루려면 대시보드(6장)를 쓴다.
- 탭이나 pane을 손으로 닫아도 된다. 다음 실행 때 사라진 것을 확인하고 상태를 정리한다.

- `down`(액션)은 프로젝트 탭을 닫는다. 대시보드의 전체 중지와 중지는 탭과 pane을 남긴다(6장).

### 배치

프로젝트의 서비스는 프로젝트 이름(또는 설정의 `tab`)을 붙인 탭 하나에서 실행한다. 탭은 `devrun`이라는 공유 space(herdr workspace) 안에 있으며, 프로젝트마다 그 space에 탭이 하나씩 추가된다. 탭의 첫 pane은 대시보드(`control-box`)이고, 서비스 pane은 그 오른쪽에 나뉜다.

### 실행 순서 (`depends_on`)

- 의존 서비스가 **준비되면** 시작한다. 준비 기준: `port`가 있으면 그 포트가 열림(다른 곳에서 띄운 서버여도 인정), 없으면 "실행 중".
- 의존 서비스가 끝나 버리면(✕ 종료됨) 기다리던 서비스는 "의존 서비스 실패"로 시작하지 않는다. 막 띄운 서비스는 5초 동안 실패로 보지 않는다.
- `start_timeout`(기본 120초)이 지나도 준비되지 않으면 "대기 시간 초과"로 시작하지 않는다. 메시지에는 기다린 의존 서비스 이름이 함께 나온다(예: `frontend (backend 준비를 기다리다 시간 초과)`). Spring Boot처럼 기동이 오래 걸리는 백엔드에는 300 이상을 권장한다. `docs/examples/ex_react_spring.json`은 300을 쓰는데, 이 값은 기동 시간을 잰 값이 아니라 예시 값이다.
- 시작하지 못한 서비스는 이유와 함께 알림(대시보드는 아래 줄)으로 보여 준다. 예: `web (dependency failed), late (timed out waiting for dependencies)`
- 대시보드에서 서비스 **하나**를 시작할 때는 직접 고른 것이므로 의존 서비스를 기다리지 않는다.

### 포트 충돌

- `port`를 이미 다른 프로세스가 쓰고 있으면 그 서비스는 시작하지 않는다. 띄워도 포트 충돌로 실패하는데, 포트는 열려 있어 "실행 중"으로 잘못 보이기 때문이다.
- 전체 시작에서는 그 서비스만 건너뛰고(`port in use`) 나머지는 시작한다.
- herdr가 새 서비스 pane에 명령을 입력하지 못하면 추가 작업을 되돌린다. 첫 서비스라
  새 탭을 만든 경우 탭을 닫고 프로젝트 상태를 삭제하며, 기존 탭에 추가한 서비스라면
  해당 pane만 닫고 상태에서도 제거한다. 이 정리는 명령 입력 실패에 적용된다. 명령이
  정상적으로 입력된 뒤 서비스 프로세스가 종료되면 로그를 확인할 수 있도록 pane은 남는다.

### 중지 대기

- Ctrl+C를 보낸 뒤 pane 셸 아래 프로세스가 끝날 때까지 0.2초 간격으로 확인하고, 끝나면 바로 기다리기를 멈춘다. `stop_timeout`(기본 10초)이 지나면 그 pane을 닫는다(남은 프로세스는 pane과 함께 종료).
- Spring Boot graceful shutdown처럼 오래 걸리는 서비스는 `stop_timeout`을 늘린다.
- 중지를 기다리는 동안 Windows 배치 파일의 "일괄 작업을 끝내시겠습니까 (Y/N)?" 질문에는 `Y`와 Enter로 답한다. 그래서 `gradlew.bat` 같은 `.bat` 서비스도 깨끗하게 멈춘다. 기다리는 동안 나온 질문만 답한다.

## 6. 대시보드

`panel` 액션을 실행하면 프로젝트의 탭에서 서비스 왼쪽, 첫 pane(`control-box`)으로 대시보드를 연다. 같은 프로젝트의 대시보드가 그 탭에 이미 있으면 새로 만들지 않고 그 탭으로 이동한다.

대시보드는 pane 셸에서 실행되는 명령이다. Ctrl+C를 누르면 대시보드가 끝나고 셸 프롬프트로 돌아오며, pane은 닫히지 않는다. 다음 `panel` 액션은 새 대시보드를 연다.

```text
 ▣ devrun · my-project                                  2/3 실행

   상태       서비스                                     포트
 ▸ ● 실행 중  backend                                    :8080
   ◐ 시작 중  frontend                                   :5173
   ○ 중지     worker

  전체 시작   전체 중지   브라우저   설정   + 추가   닫기

─ 로그 · backend ──────────────────────────────────────────────
 Started Application in 4.2 seconds
```

각 서비스 줄 끝에는 `▶ 시작` 또는 `■ 중지`, `✎ 수정`, `✕ 삭제`, `⊗`(pane 닫기) 버튼이 있다. 폭이 72칸 미만이면 아이콘만 보인다(`▶ ■ ✎ ✕ ⊗`).

### 상태

| 표시 | 의미 | 판단 기준 |
|---|---|---|
| ● 실행 중 | 동작 중 | pane 셸 아래에 실행 중인 프로세스가 있고, `port`가 열려 있음 (`port`가 없으면 프로세스만 확인) |
| ◐ 시작 중 | 뜨는 중 | 프로세스는 있지만 `port`가 아직 안 열림 |
| ✕ 종료됨 | 명령이 끝남 | pane은 있지만 셸만 남음. 실패했거나 끝난 경우라 로그를 확인한다 |
| ○ 중지 | 안 떠 있음 | pane 아래에 돌고 있는 프로세스가 없음. 중지 후에는 pane이 셸 프롬프트로 남을 수 있다 (중지 표시) |
| ◔ 대기 중 | 전체 시작에서 `depends_on`을 기다리는 중 | |
| … 처리 중 | 대시보드가 시작·중지하는 중 | |

### 조작

| 하고 싶은 것 | 마우스 | 키 |
|---|---|---|
| 서비스 선택 | 행 클릭, 휠 | `↑` `↓` `Home` `End` |
| 선택한 서비스 시작/중지 | 행 더블클릭, 그 행의 `▶ 시작`/`■ 중지` 버튼 | `Enter` |
| 선택한 서비스 재시작 | 없음 | `r` |
| 서비스 수정 | 그 행의 `✎ 수정` | 없음 |
| 서비스 삭제 | 그 행의 `✕ 삭제` | 없음 |
| 서비스 pane 닫기 | 그 행의 `⊗` | 없음 |
| 전체 시작 / 전체 중지 | 하단 줄 버튼 | `a` / `x` |
| 브라우저로 열기 (`url`) | `브라우저` 버튼 | `o` |
| 설정 파일 열기 | `설정` 버튼 | `e` |
| 대시보드 닫기 | `닫기` 버튼 | `q`, `Esc`, `Ctrl+C` |

- 한/영 상태가 한글이어도 단축키가 동작한다(ㄱ=r, ㅁ=a, ㅌ=x, ㅐ=o, ㄷ=e, ㅂ=q). 확인 창에서는 ㅛ=y, ㅜ=n 이다.
- 상태와 로그 미리보기는 1초마다 갱신된다. 로그는 선택한 서비스 pane의 최근 출력이며, pane 폭에서 접힌 줄도 원래 한 줄로 보여 준다.
- 전체 시작은 기다리는 동안에도 선택·스크롤 같은 입력을 받는다. 진행 중에 전체 중지를 누르면 남은 시작을 취소한다.
- 서비스가 많아 화면을 넘으면 선택한 행을 따라 목록이 스크롤되고, 위아래에 `▲ n more` / `▼ n more`가 보인다.
- 포트 열은 폭이 좁아 서비스 이름 열이 "서비스" 머리글과 붙어 보이게 되면 숨긴다. 기준은 머리글 글자 길이에 따라 언어마다 다르다(영어는 43칸 이하에서 숨김). 30칸 미만에서는 상태 이름을 숨기고 아이콘만 보인다.
- 줄 버튼은 72칸 이상이면 글자, 미만이면 아이콘이다. 줄 버튼이 들어가지 않을 만큼 좁으면 버튼을 숨긴다. 수정과 삭제에는 단축키가 없으니 쓰려면 창을 넓힌다.
- 예상하지 못한 오류가 나도 대시보드는 닫히지 않고 아래 줄에 요약을 보여 준다. 자세한 내용은 상태 폴더의 `panel.log`에 남는다.
- 설정 파일을 저장하면 자동으로 다시 읽는다. 형식이 틀리면 아래 줄에 오류를 띄우고 이전 설정을 유지한다.
- 설정 파일은 Windows에서는 메모장(`notepad.exe`)으로, macOS는 `open`, Linux는 `xdg-open`으로 연다.
- 중지(`Enter` 또는 시작/중지 버튼)는 그 서비스의 프로세스만 끄고, pane은 셸 프롬프트 상태로 남기며 '중지'로 표시한다. `stop_timeout` 안에 끝나지 않으면 pane을 닫는다. 전체 중지(`x`)는 실행 중인 서비스 모두에 같은 방식으로 적용되며, 탭과 컨트롤 박스는 남긴다.
- 재시작(`r`)은 서비스를 중지한 뒤 다시 시작한다. 중지했거나 끝난 pane은 같은 pane에서 명령을 다시 입력한다. `stop_timeout` 안에 프로세스가 끝나지 않았으면 pane을 닫고 새로 만든다.
- 닫기(`⊗`)는 확인 뒤 그 서비스의 pane을 닫는다. 실행 중이면 먼저 끈다. 탭과 컨트롤 박스는 남는다.
- 시작과 전체 시작은 이미 실행 중인 서비스를 건너뛰고, 완료 메시지에 "이미 실행 중: ..."으로 적는다. 실패한 서비스와는 따로 보인다.
- 대시보드를 닫아도 서비스는 계속 돈다.

### 서비스 추가·수정·삭제·닫기

`+ 추가`는 하단 줄에 있고, `✎ 수정`, `✕ 삭제`, `⊗`(닫기)는 서비스 행마다 있다. 이들에는 단축키가 없다. 추가와 수정은 안내 줄에 단계별 입력 칸이 뜨고, 고르는 중에는 로그 미리보기 자리에 선택지가 나온다.

**추가**는 다음 순서로 묻는다.

1. **분류**: 프론트엔드, 백엔드, 미들웨어, 데이터베이스, 기타. `↑` `↓` 로 고르고 `Enter` 를 누른다.
2. **기술**: 고른 분류의 프리셋 목록 (아래 표). 기타는 "직접 입력" 하나뿐이다.
3. **이름, 폴더, 명령, 포트, URL, 의존 서비스**: 기술을 고르면 명령과 포트가 채워진다. `Enter` 는 괄호 안의 값을 그대로 쓰고, `-` 는 칸을 비운다. 저장 전에 어떤 값이든 고칠 수 있다.

마지막 단계를 마치면 설정 전체를 검증한다. 검증이 실패하면(예: 포트 `99999`, 명령 비움) 파일은 바뀌지 않는다. 안내 줄에 오류가 뜨고, 입력 폼은 처음 단계부터 다시 열리며 입력했던 값이 기본값으로 남는다.

**수정**은 같은 칸을 현재 값부터 묻는다. 폼에 없는 설정(예: `env`, 시간 제한)은 그대로 둔다.

**삭제**는 확인 창 "'<이름>' 을(를) 삭제할까요?"를 띄운다. `y`를 누르거나 **삭제** 버튼을 클릭하면 지운다. `n`, `Esc`, **취소** 버튼, 또는 창 밖 클릭은 지우지 않고 닫는다. 다른 서비스의 `depends_on` 에서도 이름이 빠진다. 실행 중인 서비스는 지우지 않으며, 하단 줄에 먼저 중지하라는 안내가 나온다.

**닫기(`⊗`)**는 확인 창 "'<이름>' 창을 닫을까요?"를 띄운다. `y`를 누르거나 **닫기** 버튼을 클릭하면 그 서비스의 pane을 닫는다. 실행 중이면 먼저 끈다. 탭과 컨트롤 박스는 남으므로 나중에 같은 서비스를 다시 시작할 수 있다.

프리셋은 `src/presets.py` 에 있다. 프리셋 값은 설정 파일에 그대로 쓰이므로, 저장 전에 확인한다. Windows 명령과 Unix 명령이 다르면(예: Gradle 의 `gradlew.bat` 과 `./gradlew`) 서비스는 `command_windows` 와 `command_unix` 로 저장된다. 지금 쓰는 OS 의 명령은 입력한 값을, 다른 OS 의 명령은 프리셋 값을 쓴다.

| 분류 | 기술 | 명령 (Windows / Unix) | 포트 | 출처 |
|---|---|---|---|---|
| 프론트엔드 | React (Vite) | `npm run dev` | 없음 (고정하지 않음) | docs |
| 프론트엔드 | Next.js | `npm run dev` | 3000 | docs |
| 프론트엔드 | Vue | `npm run dev` | 5173 | 추정 (Vite 기반 create-vue 기준) |
| 프론트엔드 | Angular | `npx ng serve` | 4200 | docs |
| 프론트엔드 | Vite (기타 빌드 도구) | `npm run dev` | 5173 | docs |
| 백엔드 | Spring Boot (Gradle) | `gradlew.bat bootRun` / `./gradlew bootRun` | 8080 | docs |
| 백엔드 | Spring Boot (Maven) | `mvnw.cmd spring-boot:run` / `./mvnw spring-boot:run` | 8080 | docs |
| 백엔드 | ASP.NET Core | `dotnet run` | 5000 | 추정 (Kestrel 기본값, `launchSettings.json` 이 우선) |
| 백엔드 | PHP (built-in server) | `php -S localhost:8000` | 8000 | 추정 (매뉴얼 예시, 기본값 아님) |
| 백엔드 | PHP (Laravel) | `php artisan serve` | 8000 | 추정 (2차 자료만 확인) |
| 백엔드 | Node.js (Express) | `npm start` | 3000 | 추정 (관례이며 프레임워크 기본값은 아님) |
| 백엔드 | Django | `python manage.py runserver` / `python3 manage.py runserver` | 8000 | docs |
| 백엔드 | FastAPI | `uvicorn main:app --reload` | 8000 | 추정 (uvicorn 기본 포트는 8000, `main:app` 은 가정) |
| 미들웨어 | Redis | `redis-server` | 6379 | 추정 (문서로 확인하지 않음) |
| 데이터베이스 | PostgreSQL | `postgres -D data` | 5432 | 추정 (`data` 는 데이터 폴더 자리 표시) |
| 데이터베이스 | MySQL | `mysqld --console` / `mysqld` | 3306 | 추정 (문서로 확인하지 않음) |
| 기타 | 직접 입력 | 비움 | 비움 | — |

- **docs**: 도구의 공식 문서나 기본 설정에서 기본값을 확인했다.
- **추정**: 흔히 쓰는 값이지만 확인하지 않았다. 쓰기 전에 프로젝트에 맞는지 확인한다.
- 폴더는 프리셋이 없다. 직접 입력하지 않으면 비워 두어 프로젝트 루트를 쓴다.

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

### 예시 파일 (`docs/examples/`)

파일을 프로젝트 폴더에 `.herdr-devrun.json` 이름으로 복사한 뒤, `C:/path/to/...` 폴더와 `<DUMMY_...>` 값을 고친다. **추정**으로 표시한 항목은 내 프로젝트에서 확인하지 않은 값이므로 쓰기 전에 확인한다.

| 파일 | 서비스 | 추정 항목 |
|---|---|---|
| `ex_react_spring.json` | Spring Boot (Gradle, 8080) 과 React (pnpm, 5173) | 없음 |
| `ex_nextjs_php.json` | PHP 내장 서버 (`php -S localhost:8000`) 와 Next.js (`pnpm run dev`, 3000, php 다음에 뜸) | PHP 명령과 포트는 **추정** (Laravel 이면 `php artisan serve`) |
| `ex_vue_aspnet.json` | ASP.NET Core (`dotnet run`, 5000) 과 Vue (`npm run dev`, 5173, aspnet 다음에 뜸) | ASP.NET 포트는 **추정**: `Properties/launchSettings.json` 을 확인한다. 5173 은 Vite 기본값 |
| `ex_django_db.json` | Redis (`redis-server`, 6379) 와 Django (`python manage.py runserver 8000`, redis 다음에 뜸) | Redis 명령과 포트는 **추정** |
| `ex_spring_only.json` | Maven (`mvnw`, 8080) 으로 실행하는 Spring Boot 단독 | 8080 은 Spring 기본값: `server.port` 를 바꿨다면 고친다 |

`ex_spring_only.json` 을 Maven 대신 Gradle 로 쓰려면 두 명령 키를 아래처럼 바꾼다.

```json
"command_windows": ".\\gradlew.bat bootRun",
"command_unix": "./gradlew bootRun"
```

## 8. 수동 실행 (herdr 액션 없이)

```sh
# 플러그인 폴더에서. Windows 는 python, Linux/macOS 는 python3
python -X utf8 src/devrun.py up --dir <프로젝트 폴더>     # up / down / restart / init
python -X utf8 src/panel.py --dir <프로젝트 폴더>         # 대시보드를 지금 터미널에서 바로 실행
```

- 코드를 고친 뒤 확인하거나, 액션이 실패한 원인을 콘솔에서 바로 볼 때 쓴다. herdr CLI가 서버에 연결해야 하므로 herdr 안의 pane에서 실행한다.
- 수동 실행 상태는 Windows `%LOCALAPPDATA%\herdr-devrun`, Linux/macOS `~/.local/state/herdr-devrun`(또는 `$XDG_STATE_HOME/herdr-devrun`)에 저장된다. 액션 실행 상태(`HERDR_PLUGIN_STATE_DIR`)와 따로 관리되므로, 수동으로 띄운 것은 수동 `down`으로 내린다.

## 문서

- [Usage (English)](usage.md)
- [문제 해결](troubleshooting.md): 자주 겪는 문제
- [구조 및 동작 방식](architecture.md): 설계 세부 내용
- [개발](development.md): 코드 구조, 테스트, 설정 항목과 액션 추가
- [만든 이유와 범위](start-idea.md)
- [할 일](todo.md): 개선 목록
