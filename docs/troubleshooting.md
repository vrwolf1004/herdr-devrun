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
| 액션이 바로 실패, stderr에 `python`/`python3`를 찾을 수 없음 | Python이 PATH에 없음 | Windows는 `python`, Linux/macOS는 `python3`가 PATH에 있는지 확인한다. 설치 후 herdr 서버를 재시작한다 (`herdr server stop` → `herdr`) |
| Windows에서 `python` 실행 시 Microsoft Store가 열림 | Store 별칭(App execution alias)만 있고 실제 Python이 없음 | python.org 설치본을 설치하고 PATH에 추가하거나, 설정 → 앱 실행 별칭에서 python 별칭을 끈다 |
| `.herdr-devrun.json 을 찾을 수 없습니다` | 액션을 실행한 pane 폴더와 그 상위에 설정 파일이 없음 | 프로젝트 안의 pane에서 실행하거나 `init`으로 만든다. `herdr plugin action invoke`는 **포커스된 pane** 기준이다 |
| `services 가 없습니다` / `name, command 가 필요합니다` / `name 이 중복됩니다` | 설정 파일 내용 문제 | [usage.md](usage.md) 4장 형식대로 고친다 |
| `JSON 오류` | `\`를 하나만 씀, 끝 쉼표, 주석 사용 | `\\`로 쓰고, 끝 쉼표와 주석을 지운다 |
| `[이름] 폴더가 없습니다` | `cwd` 경로 오타, 또는 설정 파일 기준이 아닌 경로 | 설정 파일이 있는 폴더 기준 상대 경로로 쓴다 |
| Windows 액션이 안 보이거나 단축키가 안 먹음 | Linux/macOS id를 씀 | Windows는 `herdr-devrun.up-windows`처럼 `-windows`를 붙인다 |
| `up` 했는데 새 탭이 안 생기고 기존 탭으로 이동 | 이미 실행 중 | 정상 동작. 다시 띄우려면 `restart` |
| `down` 했는데 "실행 중인 서비스가 없습니다" / 대시보드에 모두 "중지" | 수동 실행(`--dir`)으로 띄웠거나, 탭을 이미 닫음 | 수동 실행과 액션은 상태를 따로 저장한다. 수동으로 띄운 것은 수동 `down`으로 내린다 |
| 탭은 닫혔는데 포트가 계속 사용 중 | 서비스가 별도 프로세스를 pane과 분리해 띄움 (예: Gradle daemon이 띄운 프로세스) | Windows: `netstat -ano \| findstr :<포트>` → `taskkill /PID <PID> /F`. Linux/macOS: `lsof -i :<포트>` → `kill <PID>` |
| 서비스가 환경변수를 못 읽음 | 새로 등록한 OS 환경변수가 herdr 서버에 반영 안 됨 | herdr 서버를 재시작한다. 또는 설정 파일 `env`에 적는다 (비밀값 제외) |
| 대시보드에서 계속 "◐ 시작 중" | `port`가 실제 포트와 다름, 또는 서버가 아직 안 뜸 | 로그 미리보기로 실제 포트를 확인해 `port`를 고친다. 저장하면 대시보드가 다시 읽는다 |
| 대시보드에서 "✕ 종료됨" | 명령이 끝났거나 실패함 (셸만 남음) | 로그 미리보기 또는 서비스 탭에서 오류를 확인하고 `↻ 재시작` |
| 대시보드 마우스 클릭이 안 먹음 | herdr 마우스 캡처가 꺼져 있거나, 클릭이 herdr 쪽에서 처리됨 | 키보드로 조작한다. herdr 설정의 `ui.mouse_capture`를 확인한다 |
| 대시보드 열 정렬이 어긋남 | 폭이 애매한 기호(●, ◐ 등)를 터미널 글꼴이 2칸으로 그림 | 터미널 글꼴을 바꾸거나 `panel.py`의 `STATUS_VIEW` 아이콘을 ASCII로 바꾼다 |
| 대시보드가 바로 닫힘 | `DEVRUN_PROJECT` 폴더에 설정 파일이 없음, 또는 시작 중 예외 | 수동 실행(`python -X utf8 src/panel.py --dir <프로젝트>`)으로 오류 메시지를 본다 |
| 대시보드를 닫은 뒤 터미널 입력이 이상함 (Linux/macOS) | 비정상 종료로 raw 모드가 복구되지 않음 | 그 pane에서 `reset` 또는 `stty sane`을 입력한다 |
| 액션 목록에 안 보임 | link/install 안 됨, disabled, herdr 버전이 0.9.0 미만 | `herdr plugin list`, `herdr plugin enable herdr-devrun`, `herdr --version` 확인 |

## 코드 수정 후 확인

```sh
# 플러그인 폴더에서. Windows 는 python, Linux/macOS 는 python3
python -m py_compile src/*.py            # 문법 검사

# 무해한 명령으로 동작 확인 (설정 파일 command 를 ping, python -m http.server 등으로)
python -X utf8 src/devrun.py up --dir <샘플 폴더>
python -X utf8 src/panel.py --dir <샘플 폴더>
python -X utf8 src/devrun.py down --dir <샘플 폴더>
```

- `link`로 등록했다면 herdr 재시작 없이 다음 액션 실행부터 수정 내용이 반영된다.
- `herdr-plugin.toml`(액션 추가 등)을 고쳤다면 `herdr plugin unlink herdr-devrun` → `herdr plugin link <플러그인 폴더>`로 다시 등록한다.
- Linux/macOS 입력 해석(`term._UnixTerminal._parse`)은 순수 로직이라 어느 OS에서든 바이트 문자열을 넣어 확인할 수 있다.
