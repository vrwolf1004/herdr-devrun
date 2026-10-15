# 구조

Python 3.8+ 표준 라이브러리만 쓴다. 매니페스트가 같은 동작을 OS별로 두 번 선언하고(Windows `python`, Linux/macOS `python3`), 모든 액션은 `src/devrun.py`를, 대시보드 pane은 `src/panel.py`를 실행한다. OS마다 다른 부분은 `procs.py`(프로세스)와 `term.py`(터미널 입력)에 모았다.

```text
herdr-plugin.toml
  ├─ [[actions]] up / down / restart / init / panel (+ -windows) ─ src/devrun.py <action>
  └─ [[panes]]   panel (+ panel-windows) ──────────────────────── src/panel.py

src/devrun.py ─┐
src/panel.py ──┼─ src/core.py ─ src/procs.py   프로세스·포트 조회 (OS별)
               └─ src/term.py                  터미널 입출력 (OS별)

src/core.py
  ├─ herdr CLI (HERDR_BIN_PATH)          탭·pane 생성, 명령 실행, 상태 조회, 알림
  ├─ <project>/.herdr-devrun.json        서비스 정의 (사용자 작성)
  └─ HERDR_PLUGIN_STATE_DIR/<hash>.json  실행 상태 (플러그인 관리)
```

## 모듈 책임

- `herdr-plugin.toml`: 플러그인 id, 지원 플랫폼, 최소 herdr 버전, 액션과 pane 선언. 명령은 셸을 거치지 않는 argv 배열이다. 모든 명령에 `-X utf8`을 붙여 OS 로캘과 상관없이 UTF-8로 입출력한다.
- `src/core.py`: 실행 흐름 없이 함수와 상수만 둔다.
  - herdr: `herdr()`(실행 + exit code 확인 + JSON의 `result` 반환), `herdr_text()`, `notify()`, `pane_id_of()`, `tab_exists()`, `live_pane_ids()`
  - config: `start_dir()`, `find_config_path()`, `read_config()`(필수 항목, 이름 중복 검사), `service_command()`(OS별 명령 선택), `tab_label()`, `service_dir()`, `env_args()`
  - state: `read_state()`, `write_state()`, `remove_state()`, `live_state()`(사라진 탭·pane 정리), `find_pane()`
  - service: `Status`, `start_service()`, `stop_service()`, `restart_service()`, `service_status()`, `service_log()`
  - project: `up()`, `down()`, `init()`과 init 감지 함수
  - `DevrunError`: 사용자에게 그대로 보여 줄 오류. 액션은 알림 + stderr + exit 1, 대시보드는 아래 줄 메시지로 보여 준다.
- `src/procs.py`: `child_process_map()`(부모 pid → 자식 프로세스 이름), `has_children()`, `is_listening()`.
- `src/term.py`: `open_terminal()`이 OS에 맞는 터미널 객체를 돌려준다. `with` 블록 안에서 대체 화면과 입력 모드를 켜고, `read(timeout)`이 `Event` 목록을 돌려준다. `size()`, `write()`.
- `src/devrun.py`: 액션 진입점(argparse). 시작 폴더와 설정 파일을 찾아 `core` 함수를 부른다. `panel` 액션은 `herdr plugin pane open`으로 대시보드 pane을 연다.
- `src/panel.py`: 대시보드. `Panel` 클래스가 화면 상태, 그리기, 입력 해석, 명령 실행을 맡는다.

## 실행 흐름

### 시작 폴더와 프로젝트 찾기

1. 액션: `--dir`가 있으면 그 폴더, 없으면 `HERDR_PANE_ID`의 pane을 `herdr pane get`으로 조회해 `cwd`를 쓴다.
2. 대시보드: `panel` 액션이 넣어 준 `DEVRUN_PROJECT` 환경변수, 수동 실행이면 `--dir`.
3. 시작 폴더에서 상위로 올라가며 `.herdr-devrun.json`을 찾는다. 찾은 파일이 있는 폴더가 **프로젝트 루트**다.
4. `init`만 예외로 상위 탐색 없이 시작 폴더에 파일을 만든다.

### 서비스 하나 시작 (`start_service`)

1. 상태를 읽고 사라진 탭·pane을 정리한다(`live_state`). 이미 떠 있으면 아무것도 하지 않는다.
2. 탭이 없으면 `herdr tab create --cwd <서비스 폴더> --label <tab> [--env ...]`로 만들고 `root_pane`을 쓴다.
3. 탭이 있으면 마지막 서비스 pane을 나눈다. 서비스 pane이 1개면 `right`, 2개 이상이면 `down`.
4. 상태에 pane을 추가해 저장하고, `herdr pane rename`(서비스 이름) → `herdr pane run`(명령 + Enter)을 보낸다.

`up`은 모든 서비스에 이 과정을 반복한다. 처음부터 띄우면 아래 배치가 되고, 일부만 떠 있으면 빠진 것만 추가된다.

```text
┌──────────────┬──────────────┐
│              │  services[1] │
│ services[0]  ├──────────────┤
│              │  services[2] │
│              ├──────────────┤
│              │  services[3] │
└──────────────┴──────────────┘
```

herdr-sidebar 같은 다른 플러그인이 탭을 만들 때 pane을 자동으로 추가할 수 있다. devrun은 자기가 만든 pane id만 추적하므로 동작에는 영향이 없다. 서비스 pane이 하나도 없이 다른 pane만 남은 탭은 닫고 새로 만든다.

### 서비스 하나 중지 (`stop_service`)

1. pane에 `herdr pane send-keys <pane> ctrl+c`를 보내고 1.5초(`STOP_WAIT_SECONDS`) 기다린다.
2. 남은 서비스가 있으면 그 pane만 `herdr pane close`, 마지막 서비스였으면 `herdr tab close` 후 상태 파일을 지운다.

재시작은 중지 후 시작이다. 같은 pane에서 다시 실행하지 않는 이유는, Windows `.bat`(gradlew 등)가 Ctrl+C 후 "일괄 작업을 끝내시겠습니까 (Y/N)?"를 물어 입력 상태가 불확실해지기 때문이다.

### 전체 중지 (`down`)

모든 서비스 pane에 Ctrl+C를 보낸 뒤 한 번만 1.5초 기다리고 탭을 닫는다. 남은 프로세스는 pane과 함께 종료된다.

### init

1. 시작 폴더와 바로 아래 폴더(`.`으로 시작하는 폴더, `node_modules`, `build`, `dist`, `target` 제외)를 검사한다.
2. 폴더마다 첫 번째로 맞는 규칙 하나를 서비스로 만든다: Gradle wrapper → Maven wrapper → `package.json`의 `dev`/`start`/`serve`. 명령은 지금 OS 형식으로 넣는다.
3. 하나도 없으면 backend/frontend 예시로 채운다. 이미 파일이 있으면 덮어쓰지 않는다.

## 상태 판정 (`service_status`)

| 상태 | 조건 |
|---|---|
| `STOPPED` | 상태 파일에 pane이 없음 (또는 pane이 사라짐) |
| `EXITED` | pane은 있지만 셸(`shell_pid`)의 자식 프로세스가 없음 (`conhost.exe` 제외) |
| `STARTING` | 자식 프로세스가 있지만 `port`에 연결되지 않음 |
| `RUNNING` | 자식 프로세스가 있고 `port`에 연결됨 (`port`가 없으면 자식 프로세스만으로 판단) |
| `WORKING` | 대시보드가 시작·중지를 처리하는 동안만 쓰는 화면용 상태 |

- Windows에서 `herdr pane process-info`의 `foreground_processes`는 셸 자신만 돌려준다. 그래서 모든 OS에서 `shell_pid`만 쓰고, 자식 프로세스는 직접 조회한다.
- 자식 프로세스 조회는 갱신마다 한 번만 하고 부모 pid별로 묶는다.

| OS | 방법 |
|---|---|
| Windows | `CreateToolhelp32Snapshot` + `Process32FirstW/NextW` (ctypes) |
| Linux | `/proc/<pid>/stat`의 ppid (comm에 공백·괄호가 있을 수 있어 마지막 `)` 기준으로 자름) |
| macOS | `ps -A -o pid=,ppid=,comm=` |

- 포트는 `127.0.0.1`, `::1`에 0.05초 제한으로 TCP 연결해 본다. 표준 라이브러리에 LISTEN 목록 API가 없어서 OS 공통으로 이 방법을 쓴다.

## 대시보드 (`panel.py`)

### 루프

```text
with terminal:   입력 모드 변경 → 대체 화면, 커서 숨김
  반복:
    read(0.15초)    ─ Event → command_for → 명령 id → execute
    1초 지났으면    ─ refresh (설정 재읽기, 상태, 선택 서비스 로그)
    바뀐 게 있으면  ─ draw
(벗어날 때 화면·입력 모드 복구)
```

- 명령 하나의 실패(`DevrunError`)는 아래 줄 메시지로만 보여 주고 루프는 계속 돈다.
- 시간이 걸리는 명령(시작·중지)은 `busy()`가 먼저 상태를 `WORKING`으로 그린 뒤 실행한다. 실행하는 동안 입력은 쌓였다가 끝난 뒤 처리된다.

### 그리기

- 매번 화면 전체를 문자열 하나로 만들어 `ESC[H`(맨 위로)부터 덮어쓰고, 줄 끝은 `ESC[K`로 지운다. 깜박임을 줄이려고 화면 전체 지우기(`ESC[2J`)는 크기가 바뀔 때만 한다.
- 색은 ANSI SGR(16색, 256색 배경)을 쓴다. 상태 → 아이콘·이름·색은 `STATUS_VIEW` 딕셔너리이고, 모든 `Status`가 들어 있는지 import 시점에 `assert`로 확인한다. 상태를 추가하고 표시를 빠뜨리면 바로 실패한다.
- `unicodedata.east_asian_width`가 `W`/`F`인 문자(한글·CJK·전각)는 2칸으로 계산한다. `fit()`이 폭에 맞춰 자르고(`…`) 공백으로 채워 열을 맞춘다.
- 그리면서 서비스 행의 y(`rows`), 버튼의 y·x 범위(`buttons`)를 기록해 두고, 마우스 좌표를 이 기록과 비교한다. 버튼은 폭이 모자라면 다음 줄로 넘어간다.

### 입력 (`term.py`)

모든 입력은 `Event(kind, key, mouse, x, y)`로 통일한다. 좌표는 0부터 센다.

| | Windows | Linux / macOS |
|---|---|---|
| 읽기 | `WaitForSingleObject` + `ReadConsoleInputW` (ctypes) | `select` + `os.read` |
| 입력 모드 | `ENABLE_WINDOW_INPUT \| ENABLE_MOUSE_INPUT \| ENABLE_EXTENDED_FLAGS` (QUICK_EDIT 끔, PROCESSED_INPUT 빼서 Ctrl+C도 키로 받음) | `tty.setraw` + xterm 마우스 보고(`ESC[?1000h`) + SGR 좌표(`ESC[?1006h`) |
| 마우스 | ConPTY가 터미널의 마우스 입력을 `MOUSE_EVENT`로 바꿔 준다. 더블클릭은 `dwEventFlags = 2` | `ESC[<b;x;yM` 해석. 같은 칸을 0.4초 안에 두 번 누르면 더블클릭으로 만든다 |
| 키 | 가상 키 코드 → 이름, 나머지는 `UnicodeChar` | `ESC[A`, `ESC OA`, `ESC[1~` 등 → 이름. 덜 들어온 시퀀스는 버퍼에 두고 다음 읽기에서 잇는다. 모르는 CSI/SS3는 끝 글자까지 버린다 |
| 크기 변경 | `WINDOW_BUFFER_SIZE_EVENT` | `SIGWINCH` |
| VT 출력 | `ENABLE_VIRTUAL_TERMINAL_PROCESSING` 켬 | 기본 |

`INPUT_RECORD`는 KEY/MOUSE 레코드가 같은 자리에 겹치는 공용체라, 16바이트 영역을 바이트로 받아 필요한 위치만 꺼낸다. 64비트에서 HANDLE이 잘리지 않도록 ctypes 함수의 인자 형식을 모두 지정한다.

## 상태 저장

- 위치: `HERDR_PLUGIN_STATE_DIR` (herdr가 액션과 플러그인 pane에 주입). 수동 실행으로 없으면 Windows `%LOCALAPPDATA%\herdr-devrun`, Linux/macOS `$XDG_STATE_HOME/herdr-devrun` 또는 `~/.local/state/herdr-devrun`.
- 파일명: 프로젝트 루트 경로의 SHA-1 앞 16자 + `.json`. Windows는 경로를 소문자로 바꿔 계산한다(대소문자 구분 없음). 프로젝트마다 하나다.
- 내용: `project`, `label`, `tab_id`, `panes[{name, pane_id}]`. pane은 서비스 `name`으로 찾으므로 설정에서 이름이 중복되면 안 된다.
- 액션과 대시보드가 같은 파일을 읽고 쓴다. 쓰기 전에 항상 최신 상태를 다시 읽어(`live_state`) 덮어쓰기 충돌을 줄인다.
- herdr 서버를 재시작하면 탭 id가 무효가 될 수 있다. `tab_exists`로 확인하고, 없으면 상태를 지운다.

## 구현 메모

- **UTF-8**: 매니페스트 명령에 `-X utf8`을 붙이고, herdr 출력은 `encoding="utf-8"`로 읽는다. 설정 파일은 BOM이 있어도 읽도록 `utf-8-sig`로 읽는다.
- **인자 전달**: `subprocess`에 인자 목록을 넘긴다. 따옴표가 든 명령도 Windows `list2cmdline`이 알맞게 감싸므로 별도 이스케이프가 없다.
- **pane id 위치**: `tab create`는 `result.root_pane.pane_id`, `pane split`은 `result.pane.pane_id`로 돌려준다. `pane_id_of()`가 둘 다 처리한다.
- **환경변수**: `--env KEY=VALUE`는 pane에서 실행되는 셸 프로세스에 들어가므로, 그 셸에서 실행하는 서비스 명령이 물려받는다.
- **플러그인 pane cwd**: `plugin pane open`에 `--cwd`를 주지 않으면 플러그인 폴더에서 실행된다. 매니페스트의 `src/panel.py` 상대 경로가 이것에 기대므로 `--cwd`를 넘기지 않는다.
- **액션 id 중복 불가**: herdr 0.9.4는 플랫폼이 달라도 같은 액션 id를 거부한다(`duplicate_plugin_action_id`). 확장자 없는 상대 경로 명령(`bin/devrun`)은 Windows에서 찾지 못해, OS별 공용 실행 파일 방식도 쓸 수 없었다.
