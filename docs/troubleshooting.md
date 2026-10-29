# 문제 해결

## 먼저 볼 것: 플러그인 로그

액션의 stdout/stderr와 exit code는 herdr가 기록한다.

```sh
herdr plugin log list --plugin herdr-devrun
```

`status: failed`인 항목의 `stderr`에 원인 메시지가 있다. 같은 메시지가 herdr 알림(`devrun 오류`)으로도 뜬다.

## 증상별

| 증상 / 메시지 | 원인 | 해결 |
|---|---|---|
| 대시보드/알림 문구가 기대한 언어가 아님 | 언어 우선순위 설정 또는 OS 언어 감지 결과 | `HERDR_DEVRUN_LANG`이 최우선이다. 없으면 `HERDR_PLUGIN_CONFIG_DIR/config.json`의 `lang`, OS 언어(Windows UI 언어 또는 `LC_ALL` / `LC_MESSAGES` / `LANG`), 영어 순으로 결정된다. `ko-KR` 같은 로케일도 가능하며, 플러그인 언어를 바꾼 뒤 액션/대시보드를 다시 실행한다 |
| 액션이 바로 실패, stderr에 `python`/`python3`를 찾을 수 없음 | Python이 PATH에 없음 | Windows는 `python`, Linux/macOS는 `python3`가 PATH에 있는지 확인한다. 설치 후 herdr 서버를 재시작한다 (`herdr server stop` → `herdr`) |
| Windows에서 `python` 실행 시 Microsoft Store가 열림 | Store 별칭(App execution alias)만 있고 실제 Python이 없음 | python.org 설치본을 설치하고 PATH에 추가하거나, 설정 → 앱 실행 별칭에서 python 별칭을 끈다 |
| `.herdr-devrun.json 을 찾을 수 없습니다` | 액션을 실행한 pane 폴더와 그 상위에 설정 파일이 없음 | 프로젝트 안의 pane에서 실행하거나 `init`으로 만든다. `herdr plugin action invoke`는 **포커스된 pane** 기준이다 |
| 스페이스는 열렸는데 서비스가 안 뜸, 또는 `control-box`가 안 보임 | 액션을 설정 파일이 없는 pane(예: `C:\work\app`)에서 실행함 | 프로젝트 폴더 안의 pane에서 실행하거나 CLI로 `--dir <프로젝트 폴더>`를 지정한다 |
| `down` 후 `up` 했더니 이전 스페이스가 화면에 없음 | 재시작하면 `devrun` 스페이스 ID가 바뀜 (예: `wW` → `wX`) | `herdr workspace list` 에서 `label: devrun` 의 새 ID를 확인하고 `herdr workspace focus <ID>` 로 포커스하거나 목록에서 클릭한다 |
| `services 가 없습니다` / `name, command 가 필요합니다` / `name 이 중복됩니다` | 설정 파일 내용 문제 | [usage.md](usage.md) 4장 형식대로 고친다 |
| 설정 오류에 `port`, `timeout`, `depends_on`이 표시됨 | 값 형식이 잘못됐거나 의존 이름/순환 문제 | [usage.md](usage.md) 4장의 검증 규칙을 확인한다. `port`는 1~65535 정수, timeout은 0 이상 숫자, `depends_on`은 존재하는 이름의 목록이어야 하며 순환할 수 없다 |
| 시작 액션이 명령을 pane에 입력하지 못했다고 실패함 | herdr가 서비스 명령을 실행 pane에 전달하지 못함 | 첫 서비스 시작 중 만들어진 탭과 상태는 정리된다. 기존 서비스 탭에 추가 중이었다면 새 pane만 닫히고 상태에서 제거된다. 반면, 명령이 입력된 뒤 프로세스가 종료된 경우 pane은 로그 확인을 위해 남는다 |
| `JSON 오류` | `\`를 하나만 씀, 끝 쉼표, 주석 사용 | `\\`로 쓰고, 끝 쉼표와 주석을 지운다 |
| `[이름] 폴더가 없습니다` | `cwd` 경로 오타, 또는 설정 파일 기준이 아닌 경로 | 설정 파일이 있는 폴더 기준 상대 경로로 쓴다 |
| Windows 액션이 안 보이거나 단축키가 안 먹음 | Linux/macOS id를 씀 | Windows는 `herdr-devrun.up-windows`처럼 `-windows`를 붙인다 |
| `up` 했는데 새 탭이 안 생기고 기존 탭으로 이동 | 이미 실행 중 | 정상 동작. 다시 띄우려면 `restart` |
| `down` 했는데 "실행 중인 서비스가 없습니다" / 대시보드에 모두 "중지" | 수동 실행(`--dir`)으로 띄웠거나, 탭을 이미 닫음 | 수동 실행과 액션은 상태를 따로 저장한다. 수동으로 띄운 것은 수동 `down`으로 내린다 |
| 탭은 닫혔는데 포트가 계속 사용 중 | 서비스가 별도 프로세스를 pane과 분리해 띄움 (예: Gradle daemon이 띄운 프로세스) | Windows: `netstat -ano \| findstr :<포트>` → `taskkill /PID <PID> /F`. Linux/macOS: `lsof -i :<포트>` → `kill <PID>` |
| 서비스가 환경변수를 못 읽음 | 새로 등록한 OS 환경변수가 herdr 서버에 반영 안 됨 | herdr 서버를 재시작한다. 또는 설정 파일 `env`에 적는다 (비밀값 제외) |
| 대시보드에서 계속 "◐ 시작 중" | `port`가 실제 포트와 다름, 또는 서버가 아직 안 뜸 | 로그 미리보기로 실제 포트를 확인해 `port`를 고친다. 저장하면 대시보드가 다시 읽는다 |
| 대시보드에서 "✕ 종료됨" | 명령이 끝났거나 실패함 (셸만 남음) | 로그 미리보기 또는 서비스 탭에서 오류를 확인하고 `r` 키(재시작)나 `▶ 시작`으로 다시 시작한다 |
| 중지했는데 pane이 남아 있음 | 대시보드의 중지는 pane을 셸 프롬프트 상태로 남긴다 | 정상 동작. 다시 시작하면 같은 pane에서 실행된다. 닫으려면 `⊗` 버튼 |
| 전체 시작에서 `이미 실행 중: <이름>` | 그 서비스 프로세스가 살아 있어 건너뜀 | 정상 동작. 다시 띄우려면 먼저 중지한다 |
| 시작하는데 pane에 `(Y/N)` 질문이 남아 있음 | 래퍼 `cmd.exe`만 남은 pane | devrun이 `Y`로 답하고 시작한다. 계속 남으면 pane을 닫고 새로 만든다 |
| `down` 후에도 `devrun` space가 남아 있음 | 다른 프로젝트의 탭이 남아 있음 | 정상 동작. 남은 탭이 없어지면 space도 닫힌다 |
| 대시보드 마우스 클릭이 안 먹음 | herdr 마우스 캡처가 꺼져 있거나, 클릭이 herdr 쪽에서 처리됨 | 키보드로 조작한다. herdr 설정의 `ui.mouse_capture`를 확인한다 |
| 대시보드 열 정렬이 어긋남 | 폭이 애매한 기호(●, ◐ 등)를 터미널 글꼴이 2칸으로 그림 | 터미널 글꼴을 바꾸거나 `panel.py`의 `STATUS_VIEW` 아이콘을 ASCII로 바꾼다 |
| 대시보드가 바로 닫힘 | 프로젝트 설정 파일을 찾지 못했거나 시작 중 예외 | `.herdr-devrun.json` 위치와 상태 폴더의 `panel.log`를 확인한다. 수동 실행(`python -X utf8 src/panel.py --dir <프로젝트>`)으로도 오류를 확인할 수 있다 |
| 대시보드 아래 줄에 `Unexpected error: ... (details: ...panel.log)` | 예상하지 못한 예외. 대시보드는 계속 돈다 | 메시지의 `panel.log` 경로에서 traceback을 확인한다. 같은 오류가 반복되면 그 내용으로 이슈를 남긴다 |
| `port N is already in use by another process` / 전체 시작에서 `(port in use)` | 다른 프로세스(이전에 띄운 서버, IDE 실행 등)가 그 포트를 쓰는 중 | 위 "포트가 계속 사용 중" 방법으로 프로세스를 찾아 끄거나, 그 서버를 그대로 쓸 거라면 무시한다(의존 대상으로는 준비된 것으로 본다) |
| 전체 시작에서 `(dependency failed)` | `depends_on` 대상이 끝나 버림(✕ 종료됨) | 의존 대상 서비스의 로그에서 실패 원인을 고친 뒤 다시 전체 시작 |
| 전체 시작에서 `(timed out waiting for <의존 서비스 이름>)` | `start_timeout` 안에 의존 대상의 `port`가 열리지 않음 | 메시지에 적힌 의존 대상의 `port`가 맞는지 확인하고, 느리게 뜨는 서비스면 `start_timeout`을 늘린다 |
| 서비스 중지가 오래 걸림 | Ctrl+C 후 프로세스가 끝나지 않아 `stop_timeout`(기본 10초)까지 기다림 | 정상 종료가 느린 서비스면 그대로 둔다. Ctrl+C를 무시하는 서비스면 `stop_timeout`을 줄인다 |
| `depends_on has a cycle` / `unknown service` | 순환 의존 또는 없는 이름 | 메시지에 나온 경로(`a → b → a`)나 이름을 고친다 |
| 대시보드를 닫은 뒤 터미널 입력이 이상함 (Linux/macOS) | 비정상 종료로 raw 모드가 복구되지 않음 | 그 pane에서 `reset` 또는 `stty sane`을 입력한다 |
| 액션 목록에 안 보임 | link/install 안 됨, disabled, herdr 버전이 0.9.0 미만 | `herdr plugin list`, `herdr plugin enable herdr-devrun`, `herdr --version` 확인 |

## 코드 수정 후 확인

```sh
# 플러그인 폴더에서. Windows 는 python, Linux/macOS 는 python3
python -m py_compile src/*.py            # 문법 검사
python -m unittest discover -s tests     # 자동 테스트 (herdr 없이 돈다)

# 무해한 명령으로 동작 확인 (설정 파일 command 를 ping, python -m http.server 등으로)
python -X utf8 src/devrun.py up --dir <샘플 폴더>
python -X utf8 src/panel.py --dir <샘플 폴더>
python -X utf8 src/devrun.py down --dir <샘플 폴더>
```

- `link`로 등록했다면 herdr 재시작 없이 다음 액션 실행부터 수정 내용이 반영된다.
- `herdr-plugin.toml`(액션 추가 등)을 고쳤다면 `herdr plugin unlink herdr-devrun` → `herdr plugin link <플러그인 폴더>`로 다시 등록한다.
- Linux/macOS 입력 해석(`term._UnixTerminal._parse`)은 순수 로직이라 어느 OS에서든 테스트로 확인한다(`tests/test_term.py`).
- 문구를 추가하면 `src/locales/*.json` 7개 모두에 같은 키를 넣는다. `tests/test_i18n.py`가 키와 `{자리표시}`가 언어마다 같은지 검사한다.
