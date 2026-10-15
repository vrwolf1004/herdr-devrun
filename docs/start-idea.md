## herdr 개발 서비스 실행 플러그인

### 한 줄 소개

프로젝트의 백엔드·프론트엔드 같은 개발 서비스를 herdr 탭 하나에 pane 별로 띄우고, 대시보드에서 하나씩 또는 한 번에 시작·중지·재시작하는 herdr 플러그인.

- 저장소: https://github.com/vrwolf1004/herdrPlugin-devrun
- 플러그인 id: `herdr-devrun`

### 배경

- herdr 플러그인 마켓에는 개발 서버 실행 플러그인(`herdr-run-targets`, `herdr-run`, `steading` 등)이 있지만, 확인 시점(2026-10) 기준 모두 `linux`, `macos`만 지원한다.
- Windows를 지원하는 `cloudmanic/herdr-plus`는 Windows에서 Go로 소스 빌드가 필요하고, 워크스페이스 템플릿이 중심이라 "서비스 실행/중지"만 원하는 용도에는 무겁다.
- 그래서 Windows, Linux, macOS에서 함께 쓰는 작은 플러그인을 직접 만든다.

### 언어 선택: PowerShell → Python

처음에는 Windows 기본 PowerShell 5.1로 만들었지만, Linux/macOS 지원을 위해 Python으로 교체했다.

| 비교 | PowerShell (5.1 + 7) | Python 3 (표준 라이브러리) |
|---|---|---|
| Linux/macOS 기본 설치 | ✕ (`pwsh` 별도 설치) | Linux 대부분 ○, macOS는 Xcode 명령줄 도구 설치 시 ○ |
| 코드 | 5.1과 7의 차이를 함께 맞춰야 함 | 한 벌 |
| 액션 시작 속도 | 0.5~1초, 대시보드는 C# 컴파일로 +1초 | 0.1초 안팎 |
| 인코딩·따옴표 | BOM, 5.1 인자 이스케이프를 따로 처리 | 거의 없음 |

### 최우선 제약

- Python 3.8+ 표준 라이브러리만 사용한다. 외부 패키지, 빌드 단계가 없다.
- 특정 프로젝트에 묶이지 않는다. 프로젝트별 차이는 모두 프로젝트 루트의 설정 파일(`.herdr-devrun.json`)로 표현한다.
- herdr와는 공식 CLI(`HERDR_BIN_PATH`)로만 통신한다. 소켓이나 내부 파일을 직접 다루지 않는다.
- 서비스 프로세스는 herdr pane 안에서 돌린다. 로그는 pane에서 바로 보고, herdr 세션이 유지되는 동안 서버도 유지된다.
- OS마다 다른 부분(프로세스 조회, 터미널 입력)은 `procs.py`, `term.py`에만 둔다.

### 범위

포함:
- `up`: 설정 파일의 서비스를 새 탭에 pane 별로 실행. 이미 실행 중이면 그 탭으로 이동
- `down`: Ctrl+C로 정상 종료 기회를 준 뒤 탭 닫기
- `restart`: down 후 up
- `init`: 폴더 구조를 보고 설정 파일 초안 생성 (Gradle, Maven, Node 패키지 감지, OS별 명령 형식)
- `panel`: GUI처럼 쓰는 대시보드 pane
  - 서비스별 상태(실행 중 / 시작 중 / 종료됨 / 중지)와 로그 미리보기
  - 서비스 하나만 시작·중지·재시작
  - 클릭할 수 있는 버튼, 행 클릭·더블클릭, 휠, 키보드 단축키
  - `port`로 실제로 떴는지 확인, `url`을 브라우저로 열기, 설정 파일을 저장하면 자동으로 다시 읽기
- OS별 명령(`command_windows`, `command_unix`)
- 결과·오류를 herdr 알림으로 표시

대시보드 제약:
- 외부 TUI 패키지 없이 ANSI 출력과 OS 입력 API로 만든다. `curses`는 Windows 표준 라이브러리에 없어 쓰지 않는다.
- 대시보드를 닫아도 서비스는 계속 돈다. 서비스는 항상 별도 탭의 pane에서 실행한다.

검증 현황:
- Windows: 액션, 대시보드(키보드, 마우스 클릭 시뮬레이션), 정리 동작까지 실제 herdr에서 확인했다.
- Linux/macOS: 입력 해석은 단위 테스트로 확인했다. 실제 herdr 환경 실행은 아직 하지 않았다.

제외 (후속 검토):
- HTTP 헬스체크(포트만 확인), 실행 순서 대기(BE가 뜬 뒤 FE 실행 등)
- 서비스 pane으로 바로 이동 (herdr 0.9.4 CLI에 특정 pane 포커스 명령이 없음)
- 설정 파일 편집 UI
