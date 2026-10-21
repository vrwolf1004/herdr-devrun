"""herdr-devrun 액션 진입점.

  up      : .herdr-devrun.json 의 services 중 안 떠 있는 것을 실행 (모두 떠 있으면 그 탭으로 이동)
  down    : 각 pane 에 Ctrl+C 를 보낸 뒤 탭을 닫는다
  restart : down 후 up
  init    : 현재 폴더(와 바로 아래 폴더)를 보고 .herdr-devrun.json 초안을 만든다
  panel   : 서비스 대시보드 pane 을 연다 (panel.py)

프로젝트 위치는 액션을 실행한 pane 의 cwd 에서 위로 올라가며 .herdr-devrun.json 을 찾는다.
수동 실행/테스트 시에는 --dir 로 시작 폴더를 지정한다.

    python src/devrun.py up --dir C:\\path\\to\\project
"""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

import core
from i18n import t

PLUGIN_ID = "herdr-devrun"
PANEL_SCRIPT = Path(__file__).resolve().parent / "panel.py"


def panel_command(project_dir):
    """pane 의 셸에 입력할 대시보드 명령. Windows 와 그 밖의 셸은 인용 규칙이 달라 OS 에 맞춰 만든다."""
    argv = [sys.executable, "-X", "utf8", str(PANEL_SCRIPT), "--dir", str(project_dir)]
    return subprocess.list2cmdline(argv) if core.IS_WINDOWS else shlex.join(argv)


def open_panel(project_dir):
    """프로젝트의 대시보드가 이미 열려 있으면 그쪽으로 포커스만 옮기고, 없으면 현재 pane 옆에 새로 연다.
    대시보드는 새 pane 의 셸에 명령을 입력해 실행한다. 끝나면(Ctrl+C) 셸 프롬프트가 남고 표식 파일은 지워진다."""
    marker = core.panel_marker_path(project_dir)
    existing = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    pane = (core.herdr("pane", "get", existing, check=False) or {}).get("pane") if existing else None
    if pane:
        core.herdr("tab", "focus", pane["tab_id"])  # 셸로 연 pane 은 plugin pane focus 로 찾을 수 없어 탭으로 옮긴다
        return

    anchor = os.environ.get("HERDR_PANE_ID")
    split = ["pane", "split", *([anchor] if anchor else []), "--direction", "right",
             "--cwd", str(project_dir), "--focus"]
    pane_id = core.pane_id_of(core.herdr(*split))
    core.herdr("pane", "run", pane_id, panel_command(project_dir))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(pane_id, encoding="utf-8")


def _config_or_none(config_path):
    """down 은 설정이 깨져 있어도 내릴 수 있어야 한다. stop_timeout 만 못 쓰고 기본값으로 기다린다."""
    try:
        return core.read_config(config_path)
    except core.DevrunError:
        return None


def run(action, explicit_dir):
    start = core.start_dir(explicit_dir)
    if action == "init":
        core.init(start)
        return

    config_path = core.find_config_path(start)
    project_dir = config_path.parent
    if action == "up":
        core.up(project_dir, core.read_config(config_path))
    elif action == "down":
        core.down(project_dir, config=_config_or_none(config_path))
    elif action == "restart":
        config = core.read_config(config_path)
        core.down(project_dir, quiet=True, config=config)
        core.up(project_dir, config)
    elif action == "panel":
        core.read_config(config_path)
        open_panel(project_dir)
    else:
        raise core.DevrunError(t("error.unknown_action", action=action))


def main():
    parser = argparse.ArgumentParser(prog="devrun")
    parser.add_argument("action", choices=["up", "down", "restart", "init", "panel"])
    parser.add_argument("--dir", help=t("cli.dir_help"))
    args = parser.parse_args()
    try:
        run(args.action, args.dir)
    except core.DevrunError as error:
        core.notify(t("notice.error_title"), str(error))
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
