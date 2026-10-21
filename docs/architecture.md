# 구조

Python 3.8+ 표준 라이브러리만 쓴다. 매니페스트가 같은 액션을 OS별로 선언하고(Windows `python`, Linux/macOS `python3`), 액션 진입점은 `src/devrun.py`다. `panel` 액션은 pane을 나눈 뒤 셸에 대시보드 명령을 실행한다. OS마다 다른 부분은 `procs.py`(프로세스)와 `term.py`(터미널 입력)에 모았다.

```text
herdr-plugin.toml
  └─ [[actions]] up / down / restart / init / panel (+ -windows) ─ src/devrun.py <action>
     [[panes]] panel (+ panel-windows) ─────────────────────────── src/panel.py (direct entrypoint)

src/devrun.py ── src/core.py ─ src/procs.py   프로세스·포트 조회 (OS별)
      │         ├─ src/term.py                터미널 입출력 (OS별)
      │         └─ src/i18n.py ─ src/locales/*.json  문구 번역
      └─ pane.split + pane.run ─ src/panel.py  대시보드

src/core.py
  ├─ herdr CLI (HERDR_BIN_PATH)          탭·pane 생성, 명령 실행, 상태 조회, 알림
  ├─ <project>/.herdr-devrun.json        서비스 정의 (사용자 작성)
  └─ HERDR_PLUGIN_STATE_DIR/<hash>.json  실행 상태 (플러그인 관리)
```

## 모듈 책임

- `herdr-plugin.toml`: 플러그인 id, 지원 플랫폼, 최소 herdr 버전, 액션과 pane 선언. 명령은 셸을 거치지 않는 argv 배열이다. 모든 명령에 `-X utf8`을 붙여 OS 로캘과 상관없이 UTF-8로 입출력한다.
- `src/core.py`: 실행 흐름 없이 함수와 상수만 둔다.
  - herdr: `herdr()`(실행 + exit code 확인 + JSON의 `result` 반환), `herdr_text()`, `notify()`, `pane_id_of()`, `tab_exists()`, `live_pane_ids()`
  - config: `start_dir()`, `find_config_path()`, `read_config()`(필수 항목, 이름 중복, 시간 값, `depends_on` 대상·순환 검사), `service_command()`(OS별 명령 선택), `tab_label()`, `service_dir()`, `env_args()`
  - state: `read_state()`, `write_state()`, `remove_state()`, `live_state()`(사라진 탭·pane 정리), `find_pane()`, `panel_marker_path()`(열린 대시보드 pane id)
  - service: `Status`, `start_service()`(포트 충돌 검사 포함), `stop_service()`, `restart_service()`, `interrupt_and_wait()`, `service_status()`(셸 pid 캐시 사용 가능), `service_log()`
  - project: `StartPlan`(depends_on 순서로 단계적 시작), `is_ready()`, `up()`, `down()`, `init()`과 init 감지 함수
  - `DevrunError`: 사용자에게 그대로 보여 줄 오류. 액션은 알림 + stderr + exit 1, 대시보드는 아래 줄 메시지로 보여 준다. `PortInUseError`는 그 하위 클래스다.
- `src/procs.py`: `child_process_map()`(부모 pid → [(자식 pid, 이름)]), `has_running_children()`, `is_listening()`, 파싱 함수 `parse_proc_stat()`, `parse_ps_line()`.
- `src/term.py`: `open_terminal()`이 OS에 맞는 터미널 객체를 돌려준다. `with` 블록 안에서 대체 화면과 입력 모드를 켜고, `read(timeout)`이 `Event` 목록을 돌려준다. `size()`, `write()`.
- `src/i18n.py`: 언어 결정, 번역 파일 로드, `t(key, **values)` 문구 치환. 지원 언어는 `en`, `ko`, `ru`, `fr`, `es`, `de`, `ja`이며 문구는 `src/locales/<언어>.json`에 둔다.
- `src/devrun.py`: 액션 진입점(argparse). 시작 폴더와 설정 파일을 찾아 `core` 함수를 부른다. `panel` 액션은 같은 프로젝트의 pane id 표식이 가리키는 pane이 있으면 해당 탭에 포커스를 둔다. 없으면 현재 pane 오른쪽에 새 pane을 나누고, 프로젝트 루트에서 실행할 `panel.py` 명령을 셸에 입력한 뒤 pane id를 표식 파일에 기록한다. 명령이 끝나면(예: Ctrl+C) `panel.py`가 표식을 지운다.
- `src/panel.py`: 대시보드. `Panel` 클래스가 화면 상태, 그리기, 입력 해석, 명령 실행을 맡는다.

## 실행 흐름

### 시작 폴더와 프로젝트 찾기

1. 액션: `--dir`가 있으면 그 폴더, 없으면 `HERDR_PANE_ID`의 pane을 `herdr pane get`으로 조회해 `cwd`를 쓴다.
2. 대시보드: `panel` 액션이 전달한 `--dir`, 수동 실행이면 직접 지정한 `--dir`.
3. 시작 폴더에서 상위로 올라가며 `.herdr-devrun.json`을 찾는다. 찾은 파일이 있는 폴더가 **프로젝트 루트**다.
4. `init`만 예외로 상위 탐색 없이 시작 폴더에 파일을 만든다.

### 서비스 하나 시작 (`start_service`)

1. 상태를 읽고 사라진 탭·pane을 정리한다(`live_state`). 이미 떠 있으면 아무것도 하지 않는다.
2. `port`가 이미 열려 있으면 `PortInUseError`. 띄워도 충돌로 실패하는데 상태는 "실행 중"으로 보이기 때문이다.
3. 탭이 없으면 `herdr tab create --cwd <서비스 폴더> --label <tab> [--env ...]`로 만들고 `root_pane`을 쓴다.
4. 탭이 있으면 마지막 서비스 pane을 나눈다. 서비스 pane이 1개면 `right`, 2개 이상이면 `down`.
5. 상태에 pane을 추가해 저장하고, `herdr pane rename`(서비스 이름) → `herdr pane run`(명령 + Enter)을 보낸다.

전체 시작(`up`, 대시보드 `a`)은 `StartPlan`으로 모든 서비스에 이 과정을 반복한다. 처음부터 띄우면 아래 배치가 되고, 일부만 떠 있으면 빠진 것만 추가된다.

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

### 전체 시작 (`StartPlan`)

`step()`을 반복 호출하면 조금씩 진행한다. `up`은 0.5초(`START_POLL_SECONDS`) 간격으로 끝날 때까지 돌리고, 대시보드는 루프의 1초 갱신마다 한 단계씩 돌려 기다리는 동안에도 입력을 받는다(스레드를 쓰지 않는다).

한 단계에서 아직 시작하지 않은 서비스마다:

1. 의존 서비스 중 실패한 것이 있거나 ✕ 종료됨이면 → `reason.dependency_failed`. 이 계획에서 막 띄운 서비스는 셸이 명령을 실행하기 전이라 잠깐 종료됨으로 보이므로 5초(`STARTUP_GRACE_SECONDS`) 동안은 실패로 보지 않는다.
2. 의존 서비스가 모두 준비됐으면(`is_ready`: `port`가 열림 — 다른 곳에서 띄운 서버도 인정, 또는 `port`가 없으면 실행 중) → `start_service`. `PortInUseError`면 `reason.port_in_use`.
3. 계획 시작 후 `start_timeout`(기본 120초)이 지났으면 → `reason.timeout`.

결과는 `started`(띄운 수)와 `failed`([(이름, 이유 키)])다. 대시보드는 기다리는 서비스를 `WAITING`으로 그린다.

### 서비스 하나 중지 (`stop_service`)

1. `interrupt_and_wait()`: pane 셸 pid를 구하고 Ctrl+C를 보낸 뒤, 셸 아래 프로세스가 끝날 때까지 0.2초(`STOP_POLL_SECONDS`) 간격으로 확인한다. 최대 `stop_timeout`(기본 10초)까지만 기다린다.
2. 남은 서비스가 있으면 그 pane만 `herdr pane close`, 마지막 서비스였으면 `herdr tab close` 후 상태 파일을 지운다.

재시작은 중지 후 시작이다. 같은 pane에서 다시 실행하지 않는 이유는, Windows `.bat`(gradlew 등)가 Ctrl+C 후 "일괄 작업을 끝내시겠습니까 (Y/N)?"를 물어 입력 상태가 불확실해지기 때문이다.

### 전체 중지 (`down`)

모든 서비스 pane에 Ctrl+C를 먼저 보내고, 서비스마다 자기 `stop_timeout`까지 함께 기다린 뒤 탭을 닫는다. 남은 프로세스는 pane과 함께 종료된다. 설정 파일이 깨져 있어도 기본값으로 내릴 수 있다.

### init

1. 시작 폴더와 바로 아래 폴더(`.`으로 시작하는 폴더, `node_modules`, `build`, `dist`, `target` 제외)를 검사한다.
2. 폴더마다 첫 번째로 맞는 규칙 하나를 서비스로 만든다: Gradle wrapper → Maven wrapper → `package.json`의 `dev`/`start`/`serve`. 명령은 지금 OS 형식으로 넣는다.
3. 하나도 없으면 backend/frontend 예시로 채운다. 이미 파일이 있으면 덮어쓰지 않는다.

## 상태 판정 (`service_status`)

| 상태 | 조건 |
|---|---|
| `STOPPED` | 상태 파일에 pane이 없음 (또는 pane이 사라짐) |
| `EXITED` | pane은 있지만 셸(`shell_pid`) 아래에 돌고 있는 프로세스가 없음 (`has_running_children`) |
| `STARTING` | 자식 프로세스가 있지만 `port`에 연결되지 않음 |
| `RUNNING` | 자식 프로세스가 있고 `port`에 연결됨 (`port`가 없으면 자식 프로세스만으로 판단) |
| `WORKING` | 대시보드가 시작·중지를 처리하는 동안만 쓰는 화면용 상태 |
| `WAITING` | 대시보드 전체 시작에서 `depends_on`을 기다리는 동안만 쓰는 화면용 상태 |

- Windows에서 `herdr pane process-info`의 `foreground_processes`는 셸 자신만 돌려준다. 그래서 모든 OS에서 `shell_pid`만 쓰고, 자식 프로세스는 직접 조회한다.
- `has_running_children`: `conhost.exe`는 무시하고, `cmd.exe`는 자기 아래에 실제 프로세스가 있을 때만 "돈다"고 본다. Windows `.bat`가 Ctrl+C 후 `cmd.exe`만 남아 Y/N을 기다리는 상태를 종료로 보기 위해서다.
- 자식 프로세스 조회는 갱신마다 한 번만 하고 부모 pid별로 묶는다. 대시보드는 pane id → 셸 pid를 캐시해 `process-info`를 다시 묻지 않는다(pane이 살아 있는 동안 셸 pid는 바뀌지 않는다).

| OS | 방법 |
|---|---|
| Windows | `CreateToolhelp32Snapshot` + `Process32FirstW/NextW` (ctypes) |
| Linux | `/proc/<pid>/stat`의 ppid (comm에 공백·괄호가 있을 수 있어 마지막 `)` 기준으로 자름) |
| macOS | `ps -A -o pid=,ppid=,comm=` |

- 포트는 `127.0.0.1`, `::1`에 각각 0.05초 제한으로 TCP 연결해 본다. 표준 라이브러리에 LISTEN 목록 API가 없어서 OS 공통으로 이 방법을 쓴다. 포트 소유 프로세스가 서비스 자식인지까지는 확인하지 않는다.

## 대시보드 (`panel.py`)

### 루프

```text
with terminal:   입력 모드 변경 → 대체 화면, 커서 숨김
  반복:
    read(0.15초)    ─ Event → command_for → 명령 id → execute
    1초 지났으면    ─ advance_plan (전체 시작 한 단계) → refresh (설정 재읽기, 상태, 선택 서비스 로그)
    바뀐 게 있으면  ─ draw
(벗어날 때 화면·입력 모드 복구)
```

- 모든 단계는 `guarded()`로 감싼다. `DevrunError`는 아래 줄 메시지로만, 예상하지 못한 예외는 요약을 메시지로 보여 주고 traceback을 상태 폴더의 `panel.log`(64KB 넘으면 뒤쪽 절반만 유지)에 남긴다. 루프는 계속 돈다.
- 루프 밖(화면 준비 등)에서 난 예외도 `panel.log`에 남기고 herdr 알림을 띄운 뒤 종료한다.
- 시간이 걸리는 명령(하나 시작·중지·재시작, 전체 중지)은 `busy()`가 먼저 상태를 `WORKING`으로 그린 뒤 실행한다. 실행하는 동안 입력은 쌓였다가 끝난 뒤 처리된다. 전체 시작만은 `StartPlan`으로 나눠 진행해 입력을 막지 않는다.
- 선택을 바꾸면 로그만 다시 읽는다(`select`). 상태 전체 조회는 1초 갱신에 맡긴다.
- 한글 자판 상태의 자모(ㄱ ㅁ ㅌ ㅐ ㄷ ㅂ)는 같은 자리의 영문 키로 바꿔 받는다.

### 그리기

- 매번 화면 전체를 문자열 하나로 만들어 `ESC[H`(맨 위로)부터 덮어쓰고, 줄 끝은 `ESC[K`로 지운다. 깜박임을 줄이려고 화면 전체 지우기(`ESC[2J`)는 크기가 바뀔 때만 한다.
- 색은 ANSI SGR(16색, 256색 배경)을 쓴다. 상태 → 아이콘·이름·색은 `STATUS_VIEW` 딕셔너리이고, 모든 `Status`가 들어 있는지 import 시점에 `assert`로 확인한다. 상태를 추가하고 표시를 빠뜨리면 바로 실패한다.
- `unicodedata.east_asian_width`가 `W`/`F`인 문자(한글·CJK·전각)는 2칸으로 계산한다. `fit()`이 폭에 맞춰 자르고(`…`) 공백으로 채워 열을 맞춘다.
- 그리면서 서비스 행의 y(`rows`), 버튼의 y·x 범위(`buttons`)를 기록해 두고, 마우스 좌표를 이 기록과 비교한다. 버튼은 폭이 모자라면 다음 줄로 넘어가고, 버튼 하나가 폭보다 넓으면 글자를 자른다.
- 목록이 화면을 넘으면 `visible_range()`가 선택한 행이 보이도록 `scroll`을 맞추고 위아래 한 줄씩 `▲`/`▼` 표시를 둔다. 로그는 최소 3줄(`MIN_LOG_LINES`)을 남긴다.
- 열 폭(`column_widths`)은 언어별 단어 길이로 계산한다. 40칸 미만은 포트 열을 숨기고, 30칸 미만은 상태를 아이콘만 보인다. 테스트가 7개 언어 × 여러 폭에서 화면 폭을 넘는 줄이 없는지 확인한다.
- 로그는 `pane read --source recent-unwrapped`로 원래 한 줄을 받아 대시보드 폭에 맞춰 자른다.

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
- **언어**: `HERDR_DEVRUN_LANG` 환경변수 → `HERDR_PLUGIN_CONFIG_DIR/config.json`의 `lang` → OS 언어 → `en` 순서로 결정한다. Windows는 사용자 UI 언어, Linux/macOS는 `LC_ALL`, `LC_MESSAGES`, `LANG` 순서로 감지한다. 지원하지 않는 언어는 다음 단계로 넘어가고, 빠진 번역 키는 영어로 대체한다.
- **플러그인 pane cwd**: 매니페스트의 직접 `panel` pane은 플러그인 폴더에서 `src/panel.py`를 실행한다. 일반 `panel` 액션은 pane을 나눈 뒤 셸에 절대 경로 명령을 실행하고, 프로젝트 루트를 `--dir`로 전달한다.
- **테스트**: `tests/`의 표준 `unittest`(`python -m unittest discover -s tests`). herdr 없이 도는 부분(입력 해석, 설정 검증, 프로세스 판정, 번역 파일, 대시보드 그리기)을 다룬다. `.github/workflows/test.yml`이 push마다 Windows/Ubuntu/macOS × Python 3.8/3.12에서 돌린다. herdr가 필요한 시작·중지 흐름은 자동 테스트가 없어 실제 herdr에서 확인한다.
- **액션 id 중복 불가**: herdr 0.9.4는 플랫폼이 달라도 같은 액션 id를 거부한다(`duplicate_plugin_action_id`). 확장자 없는 상대 경로 명령(`bin/devrun`)은 Windows에서 찾지 못해, OS별 공용 실행 파일 방식도 쓸 수 없었다.
