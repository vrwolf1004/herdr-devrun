# 개발

코드 구조, 테스트 방법, 문구와 설정을 바꿀 때 함께 고칠 곳을 정리합니다. 모듈별 역할과 실행 흐름은 [architecture.md](architecture.md)에 있습니다.

## 파일 구조

```text
herdr-devrun/
├── README.md, README.ko.md      짧은 소개 (영문, 한글)
├── herdr-plugin.toml            herdr 매니페스트: 액션과 pane 선언 (OS별)
├── LICENSE                      MIT
├── docs/                        사용법, 설정, 문제 해결, 구조, 할 일
├── src/
│   ├── devrun.py                액션 진입점 (up, down, restart, init, panel)
│   ├── core.py                  설정 읽기, 서비스 시작·중지, 상태 판정, 전체 시작 계획
│   ├── procs.py                 프로세스 트리와 포트 조사
│   ├── term.py                  OS별 터미널 입출력 (대체 화면, 키 읽기)
│   ├── panel.py                 대시보드 (화면 상태, 그리기, 입력, 명령)
│   ├── presets.py               서비스 추가 프리셋 (분류·기술별 명령과 포트)
│   ├── i18n.py                  언어 결정과 t(key, **values)
│   └── locales/<언어>.json      화면 문구 (en, ko, ru, fr, es, de, ja)
└── tests/                       unittest 테스트
    ├── support.py               테스트 공용 도구
    ├── test_config.py           설정·의존성 검사, 명령 선택
    ├── test_i18n.py             언어 파일의 키와 치환 값 검사
    ├── test_panel.py            대시보드 그리기와 입력 해석
    ├── test_procs.py            프로세스 파싱
    ├── test_process_detection.py 프로세스 트리와 종료 대기
    ├── test_state_recovery.py   상태 파일과 시작 실패 복구
    ├── test_term.py             터미널 입력 처리
    └── (기능별 test_*.py)        서비스 추가·닫기·중지, 대시보드 버튼과 확인 창, 시작 복구 등
```

## 테스트 실행

플러그인 폴더에서 실행합니다.

```sh
python -m py_compile src/core.py src/devrun.py src/i18n.py src/panel.py src/procs.py src/term.py
python -m unittest discover -s tests -v
```

`.github/workflows/test.yml`은 Windows, Linux, macOS에서 Python 3.8과 3.12로 같은 두 명령을 실행합니다. macOS의 3.8 빌드는 없어서 제외했습니다. 3.8에서도 돌아야 하므로 새 문법(예: `match`, 3.9 이상의 표준 라이브러리 함수)은 쓰지 않습니다.

## 문구를 추가하거나 바꿀 때

1. 모든 언어 파일(`src/locales/*.json`)에 같은 키를 넣습니다. `test_i18n.py`가 키 차이를 잡아 줍니다.
2. 자리표시자(`{name}`, `{count}` 등)는 모든 언어에서 같아야 합니다.
3. 코드에서는 `t("key", name=...)`으로 씁니다.
4. 대시보드 줄의 폭을 확인합니다. 한글과 일본어는 두 칸으로 셉니다(`test_panel.py`).

## 설정 항목을 추가할 때

설정 형식은 [사용법](usage.md)의 설정 표와 [usage.ko.md](usage.ko.md)에 같이 있습니다. 항목을 추가하면 다음을 함께 고칩니다.

1. `src/core.py`의 `read_config()`에서 타입과 기본값을 검사합니다. 잘못된 값은 `DevrunError`로 알려 줍니다.
2. 항목을 쓰는 함수를 고칩니다. 예: 시작 순서는 `StartPlan`, 중지 대기는 `stop_timeout()` 계열.
3. `src/locales/*.json`에 오류 문구를 추가합니다.
4. `docs/usage.md`와 `docs/usage.ko.md`의 설정 표를 같이 고칩니다.
5. `tests/test_config.py`에 정상 값과 잘못된 값 테스트를 추가합니다.

설정 파일 형식이 바뀌는 항목은 [할 일](todo.md)의 `⚙` 표시를 따릅니다. 반영 전에 형식을 확정합니다.

## 액션을 추가할 때

1. `herdr-plugin.toml`에서 Linux/macOS(`python3`)와 Windows(`python`, id에 `-windows`)를 둘 다 추가합니다. herdr는 액션 id 중복을 허용하지 않습니다.
2. `src/devrun.py`의 argparse에 명령을 추가합니다.
3. 사용법 문서(`usage.md`, `usage.ko.md`)의 액션 id 표를 고칩니다.

## 문서 맞추기

- `usage.md`(영문)와 `usage.ko.md`(한국어)는 같은 내용을 가져야 합니다. 한쪽을 고치면 다른 쪽도 고칩니다.
- `architecture.md`는 구조와 동작 방식을, 이 문서는 개발 절차를 다룹니다. 중복되는 설명은 한쪽에만 두고 링크합니다.
- 액션이나 설정 항목을 바꾸면 [문제 해결](troubleshooting.md)의 증상 표도 확인합니다.

## 커밋 전 확인

- 위 `py_compile`과 `unittest` 두 명령이 모두 통과하는지 확인합니다.
- 대시보드 문구나 키를 바꿨다면 실제 터미널에서 한 번 실행해 봅니다. 자동 테스트만으로는 줄 맞춤과 키 입력을 확인할 수 없습니다.
