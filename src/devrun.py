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
import sys

import core

PLUGIN_ID = "herdr-devrun"
# 매니페스트의 [[panes]] id. 액션 id 는 OS 별로 중복 선언할 수 없어 Windows 쪽에 -windows 를 붙였다.
PANEL_ENTRYPOINT = "panel-windows" if core.IS_WINDOWS else "panel"


def open_panel(project_dir):
    args = ["plugin", "pane", "open", "--plugin", PLUGIN_ID, "--entrypoint", PANEL_ENTRYPOINT,
            "--placement", "split", "--direction", "right", "--focus", "--env", f"DEVRUN_PROJECT={project_dir}"]
    pane_id = os.environ.get("HERDR_PANE_ID")
    if pane_id:
        args += ["--target-pane", pane_id]
    core.herdr(*args)


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
        core.down(project_dir)
    elif action == "restart":
        config = core.read_config(config_path)
        core.down(project_dir, quiet=True)
        core.up(project_dir, config)
    elif action == "panel":
        core.read_config(config_path)
        open_panel(project_dir)
    else:
        raise core.DevrunError(f"알 수 없는 액션: {action}")


def main():
    parser = argparse.ArgumentParser(prog="devrun")
    parser.add_argument("action", choices=["up", "down", "restart", "init", "panel"])
    parser.add_argument("--dir", help="pane cwd 대신 쓸 시작 폴더")
    args = parser.parse_args()
    try:
        run(args.action, args.dir)
    except core.DevrunError as error:
        core.notify("devrun 오류", str(error))
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
